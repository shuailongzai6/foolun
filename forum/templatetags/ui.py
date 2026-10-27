from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, extra=""):
    """引用 static/icons.svg 中的符号；图标集单独缓存，不随每个页面重复下载。"""
    return format_html('<svg class="{}" aria-hidden="true" focusable="false"><use href="{}#i-{}"></use></svg>', f"icon {extra}".strip(), static("icons.svg"), name)


@register.simple_tag
def avatar(person, size="md"):
    return format_html('<span class="avatar avatar-{} tone-{}" aria-hidden="true">{}</span>', size, person.avatar_color, person.initial)
