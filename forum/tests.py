from django.test import TestCase, override_settings

from accounts.models import User

from .text import render_markdown


class CommunityAccessTests(TestCase):
    def test_markdown_removes_active_html(self):
        html = str(render_markdown('<script>alert(1)</script><p onclick="alert(2)">你好</p> [链接](javascript:alert(3))'))
        self.assertNotIn("<script", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("javascript:", html)
        self.assertIn("你好", html)

    @override_settings(DEBUG=False)
    def test_demo_accounts_cannot_authenticate_in_production(self):
        user = User.objects.create_user("demo_lock", password="Demo_password_2026!", is_demo=True)
        self.assertFalse(user.is_verified)
        self.assertFalse(self.client.login(username="demo_lock", password="Demo_password_2026!"))
