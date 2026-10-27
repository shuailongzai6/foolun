import markdown
import nh3
from django.utils.safestring import mark_safe


def render_markdown(text):
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "sane_lists"])
    return mark_safe(nh3.clean(
        html,
        tags={"p", "br", "hr", "strong", "em", "del", "blockquote", "ul", "ol", "li", "h2", "h3", "h4", "pre", "code", "a", "table", "thead", "tbody", "tr", "th", "td"},
        attributes={"a": {"href", "title"}},
        url_schemes={"http", "https", "mailto"},
        link_rel="nofollow noopener noreferrer",
    ))
