from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from forum.models import Post

from .forms import RegistrationForm, ReportUploadForm, SettingsForm
from .models import User
from .services import bind_education, verify_upload


def register(request):
    if request.user.is_authenticated:
        return redirect("forum:home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("username", "这个用户名已被使用，请换一个。")
        else:
            login(request, user, backend="accounts.backends.CommunityBackend")
            messages.success(request, "欢迎来到同窗。你可以先浏览公开讨论，再绑定学历参与交流。")
            return redirect("forum:home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def settings(request):
    form = SettingsForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "设置已保存，首页推荐会使用新的偏好。")
        return redirect("accounts:settings")
    return render(request, "accounts/settings.html", {"form": form, "tiers": [{"rank": tier.pk, "name": tier.name} for tier in form.tiers]})


@login_required
def certification(request):
    form = ReportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            result = verify_upload(form.cleaned_data["report"])
            education = bind_education(request.user, result)
        except ValueError as exc:
            form.add_error("report", str(exc))
        else:
            messages.success(request, f"已绑定{education.school.label}的学历。其他已绑定学历会继续保留。")
            return redirect("accounts:settings")
    return render(request, "accounts/certification.html", {"form": form})


def profile(request, username):
    person = get_object_or_404(User, username=username, is_active=True)
    posts = Post.objects.cards(request.user).filter(author=person).order_by("-created_at")
    return render(request, "accounts/profile.html", {"person": person, "page_obj": Paginator(posts, 12).get_page(request.GET.get("page"))})
