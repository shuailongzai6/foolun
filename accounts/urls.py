from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", views.settings, name="settings"),
    path("certification/", views.certification, name="certification"),
    path("password/", auth_views.PasswordChangeView.as_view(template_name="accounts/password.html", success_url="/accounts/settings/"), name="password"),
    path("u/<str:username>/", views.profile, name="profile"),
]
