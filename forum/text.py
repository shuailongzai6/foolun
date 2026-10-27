import re
from html import unescape

import markdown
import nh3
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator


def render_markdown(text):
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    return mark_safe(nh3.clean(
        html,
        tags={"p", "br", "hr", "strong", "em", "del", "blockquote", "ul", "ol", "li", "h2", "h3", "h4", "pre", "code", "a", "table", "thead", "tbody", "tr", "th", "td"},
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
        link_rel="nofollow noopener noreferrer",
    ))


def summarize(html, length=160):
    """纯文本摘要：解码实体并合并空白，输出时再由模板统一转义。"""
    text = " ".join(unescape(strip_tags(html)).split())
    # 段落合并后，全角标点两侧不需要空格。
    text = re.sub(r" ?([　-〿＀-￯]) ?", r"\1", text)
    return Truncator(text).chars(length)
