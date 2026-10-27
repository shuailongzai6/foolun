from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Education, School, SchoolTier, User


@admin.register(User)
class CampusUserAdmin(UserAdmin):
    list_display = ("username", "display_name", "is_staff", "date_joined")
    fieldsets = UserAdmin.fieldsets + (
        ("公开资料", {"fields": ("display_name", "bio")}),
        ("首页偏好", {"fields": ("home_min_tier", "home_max_tier")}),
    )


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "tier")
    list_filter = ("tier",)
    list_editable = ("tier",)
    search_fields = ("name", "short_name")


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "education_level", "status", "verified_at")
    list_filter = ("status", "school__tier")
    search_fields = ("user__username", "school__name")
    readonly_fields = ("user", "school", "major", "education_level", "status", "enrollment_year", "graduation_year", "expected_graduation_year", "verified_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SchoolTier)
