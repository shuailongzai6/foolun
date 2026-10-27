from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class SchoolTier(models.Model):
    rank = models.PositiveSmallIntegerField("等级顺序", primary_key=True)
    name = models.CharField("等级名称", max_length=40, unique=True)

    class Meta:
        ordering = ["rank"]
        verbose_name = "学校等级"
        verbose_name_plural = "学校等级"

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField("学校名称", max_length=150, unique=True)
    short_name = models.CharField("简称", max_length=20, blank=True)
    tier = models.ForeignKey(SchoolTier, null=True, blank=True, on_delete=models.PROTECT, verbose_name="学校等级")

    class Meta:
        ordering = ["name"]
        verbose_name = "学校"
        verbose_name_plural = "学校"

    def __str__(self):
        return self.name

    @property
    def label(self):
        return self.short_name or self.name


class User(AbstractUser):
    display_name = models.CharField("昵称", max_length=30, blank=True)
    bio = models.CharField("个人简介", max_length=240, blank=True)
    is_demo = models.BooleanField(default=False, editable=False)
    home_min_tier = models.ForeignKey(SchoolTier, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="首页覆盖最低等级")
    home_max_tier = models.ForeignKey(SchoolTier, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="首页覆盖最高等级")

    class Meta(AbstractUser.Meta):
        constraints = [models.CheckConstraint(
            condition=(models.Q(home_min_tier__isnull=True, home_max_tier__isnull=True)
                       | models.Q(home_min_tier__isnull=False, home_max_tier__isnull=False, home_min_tier__lte=models.F("home_max_tier"))),
            name="valid_home_tier_interval",
        )]

    @property
    def name(self):
        return self.display_name or self.username

    @property
    def initial(self):
        return self.name[:1].upper()

    @property
    def avatar_color(self):
        return (self.pk or 0) % 5

    @property
    def is_verified(self):
        return bool(self.verified_educations)

    @cached_property
    def verified_educations(self):
        records = getattr(self, "_active_educations", None)
        return records if records is not None else list(self.educations.active().select_related("school__tier"))

    @property
    def school_ids(self):
        return {education.school_id for education in self.verified_educations}

    @property
    def school_tier_ranks(self):
        return {education.school.tier_id for education in self.verified_educations if education.school.tier_id is not None}

    @property
    def schools(self):
        return list({education.school_id: education.school for education in self.verified_educations}.values())

    @property
    def schools_label(self):
        return "、".join(school.label for school in self.schools)


class EducationQuerySet(models.QuerySet):
    def active(self):
        return self.all() if settings.DEBUG else self.filter(is_demo=False)


class Education(models.Model):
    class Status(models.TextChoices):
        STUDENT = "student", "在校生"
        ALUMNI = "alumni", "校友"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="educations", verbose_name="所属账户")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="educations", verbose_name="学校")
    major = models.CharField("专业", max_length=150, blank=True)
    education_level = models.CharField("学历层次", max_length=40, blank=True)
    status = models.CharField("身份", max_length=10, choices=Status)
    enrollment_year = models.PositiveSmallIntegerField("入学年份", null=True, blank=True)
    graduation_year = models.PositiveSmallIntegerField("毕业年份", null=True, blank=True)
    expected_graduation_year = models.PositiveSmallIntegerField("预计毕业年份", null=True, blank=True)
    verified_at = models.DateTimeField("核验时间", default=timezone.now)
    is_demo = models.BooleanField(default=False, editable=False)

    objects = EducationQuerySet.as_manager()

    class Meta:
        ordering = ["-verified_at", "id"]
        verbose_name = "绑定学历"
        verbose_name_plural = "绑定学历"

    def __str__(self):
        return f"{self.school.label} · {self.education_level} · {self.major}"


class EducationIdentity(models.Model):
    fingerprint = models.CharField(max_length=64, primary_key=True, editable=False)
    education = models.ForeignKey(Education, on_delete=models.CASCADE, related_name="identities")
    kind = models.CharField("标识类型", max_length=20)

    class Meta:
        verbose_name = "学历去重标识"
        verbose_name_plural = "学历去重标识"
