from django.contrib import admin

from .models import Comment, Notification, Post, Topic


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "topic", "access_mode", "created_at")
    list_filter = ("topic", "kind", "access_mode")
    search_fields = ("title", "body", "author__username")
    readonly_fields = ("access_mode", "read_min_tier", "read_max_tier", "reply_min_tier", "reply_max_tier")


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "slug", "position")


admin.site.register(Comment)
admin.site.register(Notification)
admin.site.site_header = "同窗 · 管理后台"
admin.site.site_title = "同窗管理"
