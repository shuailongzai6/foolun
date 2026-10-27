from django.test import TestCase, override_settings

from accounts.models import Education, School, User

from .models import Comment, Post, Topic
from .text import render_markdown
from .views import comment_threads


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


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class DiscussionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("reader", password="Reader_password_2026!")
        Education.objects.create(user=cls.user, school=School.objects.create(name="测试大学"), status=Education.Status.STUDENT)
        cls.post = Post.objects.create(author=cls.user, topic=Topic.objects.first(), title="标题", body="**加粗**\n\n1 < 2")

    def test_rendered_body_follows_edits(self):
        self.assertIn("<strong>加粗</strong>", self.post.html)
        self.assertEqual(self.post.excerpt, "加粗 1 < 2")
        self.post.body = "新的正文"
        self.post.save(update_fields=["body"])
        self.post.refresh_from_db()
        self.assertEqual((self.post.body_html, self.post.excerpt), ("<p>新的正文</p>", "新的正文"))

    def test_nested_replies_are_flattened_under_their_root(self):
        root = Comment.objects.create(post=self.post, author=self.user, body="一楼")
        reply = Comment.objects.create(post=self.post, author=self.user, parent=root, body="回复")
        deeper = Comment.objects.create(post=self.post, author=self.user, parent=reply, body="再回复")
        [thread] = comment_threads(self.post, self.user, "best")
        self.assertEqual([item.pk for item in thread.thread], [reply.pk, deeper.pk])

    def test_htmx_reply_refreshes_discussion(self):
        self.client.force_login(self.user)
        response = self.client.post(f"/posts/{self.post.pk}/reply/", {"body": "局部刷新"}, headers={"HX-Request": "true"})
        self.assertContains(response, 'id="discussion"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertIn("toast", response.headers["HX-Trigger"])
        self.assertEqual(self.post.comments.get().body, "局部刷新")
