import hashlib
import hmac
import json
import re
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from pypdf.errors import PyPdfError

from verify_report import compact, comparable_value, verify_report

from .models import Education, EducationIdentity, School


def verify_upload(upload):
    # 上传报告只在核验期间存在于临时目录，不保留 PDF 和身份字段。
    with NamedTemporaryFile(suffix=".pdf") as temporary:
        for chunk in upload.chunks():
            temporary.write(chunk)
        temporary.flush()
        try:
            result = verify_report(temporary.name)
        except (OSError, ValueError, PyPdfError) as exc:
            raise ValueError("报告无法读取，请上传学信网下载的原版文字 PDF。") from exc
    if not result["verified"]:
        if "error" in result:
            raise ValueError(result["error"])
        labels = "、".join(item["field"] for item in result["differences"])
        raise ValueError(f"报告与官网不一致：{labels}。请重新下载报告。")
    return result


def education_identities(result):
    """同一学籍/学历的多个稳定标识；验证码、专业和预计毕业日期不参与去重。"""
    fields = result["official_fields"]
    school = compact(fields["学校名称"])
    level = re.split(r"[（(]", compact(fields.get("层次", "")))[0]
    level = {"硕士研究生": "硕士", "博士研究生": "博士", "大专": "专科"}.get(level, level)
    admission = comparable_value("入学日期", fields.get("入学日期", ""))
    candidates = []
    for label in ("证书编号", "补证编号"):
        if fields.get(label):
            candidates.append(("certificate", [school, compact(fields[label])]))
    if fields.get("学号"):
        candidates.append(("student", [school, compact(fields["学号"]), level]))
    enrollment = [school, compact(fields.get("姓名", "")), comparable_value("出生日期", fields.get("出生日期", "")), admission, level]
    if all(enrollment):
        candidates.append(("enrollment", enrollment))
    if not candidates:
        raise ValueError("报告缺少用于识别同一学历的稳定字段，请使用包含完整信息的学信网报告。")
    identities = {}
    for kind, values in candidates:
        payload = json.dumps(["v1", kind, *values], ensure_ascii=False, separators=(",", ":"))
        fingerprint = hmac.new(settings.EDUCATION_IDENTITY_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        identities[fingerprint] = kind
    return identities


def bind_education(user, result):
    if result.get("verified") is not True:
        raise ValueError("报告尚未通过学信网核验。")
    identities = education_identities(result)
    try:
        with transaction.atomic():
            matches = list(EducationIdentity.objects.select_related("education").filter(fingerprint__in=identities).order_by("education_id"))
            if any(item.education.user_id != user.pk for item in matches):
                raise ValueError("这份学历已经绑定到另一个账号，不能重复绑定。")
            education = matches[0].education if matches else Education(user=user)
            # 同一账号上传学籍与学历报告时，可以将它们识别出的别名归入一份学历。
            duplicates = {item.education_id for item in matches} - {education.pk}
            if duplicates:
                EducationIdentity.objects.filter(education_id__in=duplicates).update(education=education)
                Education.objects.filter(pk__in=duplicates).delete()
            fields, extracted = result["official_fields"], result["education"]
            education.school, _ = School.objects.get_or_create(name=extracted["school"])
            education.major = fields.get("专业", "")
            education.education_level = fields.get("层次", "")
            status = fields.get("学籍状态", "")
            is_alumni = education.status == Education.Status.ALUMNI or "备案表" in result["report_type"] or "毕业" in status or "结业" in status
            education.status = Education.Status.ALUMNI if is_alumni else Education.Status.STUDENT
            for field in ("enrollment_year", "graduation_year", "expected_graduation_year"):
                setattr(education, field, extracted[field] or getattr(education, field))
            education.verified_at, education.is_demo = timezone.now(), False
            education.save()
            known = {item.fingerprint for item in matches}
            EducationIdentity.objects.bulk_create([
                EducationIdentity(fingerprint=fingerprint, education=education, kind=kind)
                for fingerprint, kind in identities.items() if fingerprint not in known
            ])
            if user.is_demo:
                user.is_demo = False
                user.save(update_fields=["is_demo"])
    except IntegrityError as exc:
        # 唯一约束负责拦截并发绑定；整个事务回滚，不留下半份学历。
        raise ValueError("这份学历刚刚被绑定，请刷新后重试。") from exc
    user.__dict__.pop("verified_educations", None)
    user.__dict__.pop("_active_educations", None)
    return education
