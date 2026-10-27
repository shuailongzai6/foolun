"""提取学信网 PDF 报告，查询官方结果并逐项比对。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PyPdfError


VERIFY_URL = "https://www.chsi.com.cn/xlcx/bg.do"
REPORT_TYPES = ("教育部学籍在线验证报告", "教育部学历证书电子注册备案表")
LABEL_ALIASES = {
    "学历证书编号": "证书编号", "毕业证书编号": "证书编号",
    "院校": "学校名称", "毕业院校": "学校名称", "专业名称": "专业", "学历层次": "层次",
    "形式": "学习形式", "类型": "学历类别", "入学时间": "入学日期", "毕业时间": "毕（结）业日期",
    "毕业日期": "毕（结）业日期",
    "毕(结)业日期": "毕（结）业日期", "毕(结)业": "毕（结）业", "校(院)长姓名": "校（院）长姓名",
}
TABLE_LABELS = {
    "姓名", "性别", "出生日期", "民族", "国籍", "证件号码", "学校名称", "层次", "专业",
    "学制", "学历类别", "学习形式", "分院", "系所", "院系", "班级", "学号", "入学日期",
    "学籍状态", "预计毕业日期", "毕业日期", "毕（结）业日期", "毕（结）业", "证书编号",
    "校（院）长姓名", "补证学校", "补证日期", "补证编号", "院校所在地", "在线验证码", *LABEL_ALIASES,
}


class ReportError(ValueError):
    """报告无法完整解析，或官网查询失败。"""


@dataclass(frozen=True)
class Report:
    report_type: str
    fields: dict[str, str]

    @property
    def verification_code(self) -> str:
        return self.fields["在线验证码"]


def compact(value: str) -> str:
    """去除 PDF 排版和 HTML 换行引入的空白，不修改字段内容。"""
    return re.sub(r"\s+", "", value)


def canonical_label(label: str) -> str:
    label = compact(label).rstrip("：:")
    return LABEL_ALIASES.get(label, label)


def comparable_value(field: str, value: str) -> str:
    value = compact(value)
    if field.endswith("日期"):
        match = re.fullmatch(r"(\d{4})(?:年|[-/.])(\d{1,2})(?:月|[-/.])(\d{1,2})日?", value)
        if match:
            try:
                return date(*map(int, match.groups())).isoformat()
            except ValueError:
                pass
    return value


def report_type(text: str) -> str:
    for title in REPORT_TYPES:
        if title in compact(text):
            return title
    raise ReportError("未找到支持的学信网报告标题。")


def add_field(fields: dict[str, str], label: str, value: str, source: str) -> None:
    label = canonical_label(label)
    if not label or label in fields:
        raise ReportError(f"{source}出现空白或重复字段：{label}。")
    fields[label] = value.strip()


def extract_report(path: str | Path) -> Report:
    reader = PdfReader(path)
    text = "\n".join(page.extract_text(extraction_mode="layout") for page in reader.pages)
    title = report_type(text)
    code = re.search(r"在线验证码\s*[：:]?\s*([A-Za-z0-9]+)", text)
    if code is None:
        raise ReportError("PDF 中没有可读取的在线验证码；请使用学信网下载的文字版 PDF。")

    fields = {}
    # 验证码之前是正文。保留未知字段，不能将新字段或被修改的标签静默丢弃。
    for line in text[: code.start()].splitlines():
        if not line.strip() or compact(line) == title or re.match(r"\s*更新日期\s*[：:]", line):
            continue
        cells = re.split(r"\s{2,}", line.strip())
        while cells:
            label = cells.pop(0)
            # 奇数个单元格意味着某个空值在 PDF 排版文本中消失。
            if cells and len(cells) % 2 == 0 and compact(cells[0]).rstrip("：:") in TABLE_LABELS:
                value = ""
            elif cells:
                value = cells.pop(0)
            elif compact(label).rstrip("：:") in TABLE_LABELS:
                value = ""
            else:
                raise ReportError("PDF 正文存在无法完整读取的行，请使用学信网原版文字 PDF。")
            add_field(fields, label, value, "PDF")

    updated = re.search(r"更新日期\s*[：:]?\s*([^\s]+)", text)
    if updated:
        fields["更新日期"] = updated.group(1)
    fields["在线验证码"] = code.group(1)
    if not {"学校名称", "专业"} <= fields.keys() or not compact(fields.get("学校名称", "")):
        raise ReportError("无法完整读取学校和专业；当前解析器需要报告正文的文字表格。")

    # PDF 显示的验证码必须与其内嵌官方验证链接一致。
    for page in reader.pages:
        for reference in page.get("/Annots", []):
            action = reference.get_object().get("/A")
            uri = action.get("/URI", "") if action else ""
            url = urlsplit(uri)
            if url.hostname == "www.chsi.com.cn" and url.path == "/xlcx/bg.do":
                linked_code = parse_qs(url.query).get("vcode", [""])[0]
                if linked_code != fields["在线验证码"]:
                    raise ReportError("PDF 显示的在线验证码与内嵌官方验证链接不一致。")

    return Report(title, fields)


def parse_official_report(html: str) -> Report:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(".report-info-item")
    fields = {}
    for item in items:
        label_node, value_node = item.select_one(".label"), item.select_one(".value")
        if label_node is None or value_node is None:
            raise ReportError("官网报告结构发生变化，无法完整读取字段。")
        add_field(fields, label_node.get_text(strip=True), value_node.get_text(" ", strip=True), "官网报告")

    # 学历备案表及旧版报告采用表格，每行可有多组字段。
    if not items:
        for table in soup.find_all("table"):
            rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
            labels = {canonical_label(cell.get_text()) for row in rows for cell in row.find_all(["th", "td"], recursive=False)}
            if not {"学校名称", "专业"} <= labels:
                continue
            for row in rows:
                cells = [cell for cell in row.find_all(["th", "td"], recursive=False) if not (cell.find("img") and not cell.get_text(strip=True))]
                if not cells or (len(cells) == 1 and compact(cells[0].get_text()) in REPORT_TYPES):
                    continue
                if len(cells) % 2:
                    raise ReportError("官网报告表格结构无法完整读取，没有完成核验。")
                for label, value in zip(cells[::2], cells[1::2]):
                    add_field(fields, label.get_text(), value.get_text(" ", strip=True), "官网报告")
            break

    if not {"学校名称", "专业"} <= fields.keys() or not compact(fields.get("学校名称", "")):
        raise ReportError("官网未返回可核验报告：可能已过期、验证码无效或需要人工验证。")

    code = soup.select_one(".yzm")
    if code:
        fields["在线验证码"] = code.get_text(strip=True)
    elif "在线验证码" not in fields:
        match = re.search(r"在线验证码\s*[：:]?\s*([A-Za-z0-9]+)", soup.get_text(" ", strip=True))
        if match is None:
            raise ReportError("官网报告缺少在线验证码，无法确认查询结果。")
        fields["在线验证码"] = match.group(1)
    updated = soup.select_one(".update-time")
    if updated:
        fields["更新日期"] = re.sub(r"^更新日期\s*[：:]?\s*", "", updated.get_text(strip=True))
    else:
        match = re.search(r"更新日期\s*[：:]?\s*([^\s]+)", soup.get_text(" ", strip=True))
        if match:
            fields["更新日期"] = match.group(1)

    headings = soup.select("h1, h2, h3, caption, .report-title, title")
    heading = next((node for node in headings if any(title in compact(node.get_text()) for title in REPORT_TYPES)), None)
    return Report(report_type(heading.get_text() if heading else ""), fields)


def fetch_official_report(verification_code: str, *, timeout: float = 20) -> Report:
    try:
        response = httpx.get(
            VERIFY_URL,
            params={"vcode": verification_code, "ln": "cn", "srcid": "pdf"},
            timeout=timeout,
        )
    except httpx.TimeoutException as exc:
        raise ReportError("学信网查询超时，请稍后重试。") from exc
    except httpx.RequestError as exc:
        raise ReportError(f"学信网网络请求失败：{type(exc).__name__}。") from exc
    if response.status_code != 200:
        raise ReportError(f"学信网查询失败（HTTP {response.status_code}），没有完成真实性核验。")
    return parse_official_report(response.text)


def compare_reports(original: Report, official: Report) -> list[dict[str, str | None]]:
    original_fields = {"报告类型": original.report_type, **original.fields}
    official_fields = {"报告类型": official.report_type, **official.fields}
    differences = []
    # 双向比较：字段被删除、提取遗漏、官网缺失字段，都不能判为通过。
    for field in dict.fromkeys([*original_fields, *official_fields]):
        before, after = original_fields.get(field), official_fields.get(field)
        if before is None or after is None or comparable_value(field, before) != comparable_value(field, after):
            differences.append({"field": field, "original": before, "official": after})
    return differences


def education_fields(fields: dict[str, str]) -> dict:
    def year(*labels: str) -> int | None:
        value = next((fields[label] for label in labels if fields.get(label)), "")
        match = re.match(r"\d{4}", value)
        return int(match.group()) if match else None

    return {
        # 学校作为权限身份使用统一名称；原始排版值仍保留在 fields 中。
        "school": compact(fields.get("学校名称", "")) or None,
        "major": fields.get("专业"),
        "enrollment_year": year("入学日期"),
        "graduation_year": year("毕（结）业日期", "毕(结)业日期", "毕业日期"),
        "expected_graduation_year": year("预计毕业日期"),
    }


def verify_report(path: str | Path) -> dict:
    original = extract_report(path)
    result = {
        "verified": False,
        "report_type": original.report_type,
        "fields": original.fields,
        "education": education_fields(original.fields),
    }
    try:
        official = fetch_official_report(original.verification_code)
    except ReportError as exc:
        return {**result, "error": str(exc)}
    differences = compare_reports(original, official)
    return {
        **result,
        "verified": not differences,
        "official_fields": official.fields,
        "differences": differences,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="学信网报告 PDF 路径")
    parser.add_argument("--output", type=Path, help="将 JSON 结果写入文件")
    args = parser.parse_args()
    try:
        result = verify_report(args.report)
    except (OSError, ValueError, PyPdfError) as exc:
        result = {"verified": False, "error": str(exc)}

    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 2 if "error" in result else 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
