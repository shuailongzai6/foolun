from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import SchoolTier, User


class ReportUploadForm(forms.Form):
    report = forms.FileField(
        label="学信网验证报告", widget=forms.FileInput(attrs={"accept": ".pdf,application/pdf"})
    )

    def clean_report(self):
        report = self.cleaned_data["report"]
        if report.size > 5 * 1024 * 1024:
            raise forms.ValidationError("请上传不超过 5 MB 的 PDF。")
        return report


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "display_name", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "日常登录使用的用户名", "autocomplete": "username"}),
            "display_name": forms.TextInput(attrs={"placeholder": "大家在社区里看到的名字"}),
        }


class SettingsForm(forms.ModelForm):
    filter_home = forms.BooleanField(label="首页推荐的阅读权限需要覆盖以下等级", required=False)

    class Meta:
        model = User
        fields = ("display_name", "bio", "home_min_tier", "home_max_tier")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "placeholder": "简单介绍一下自己，或写下最近感兴趣的事。"}),
            "home_min_tier": forms.HiddenInput, "home_max_tier": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["filter_home"].initial = self.instance.home_min_tier_id is not None
        self.tiers = list(SchoolTier.objects.all())

    def clean(self):
        data = super().clean()
        if not data.get("filter_home"):
            data["home_min_tier"] = data["home_max_tier"] = None
        else:
            low, high = data.get("home_min_tier"), data.get("home_max_tier")
            if low is None or high is None or low.pk > high.pk:
                raise forms.ValidationError("请选择有效的首页等级区间。")
        return data
