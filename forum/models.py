from django.conf import settings
from django.db import models
from django.db.models import Count, Exists, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from accounts.models import Education

from .text import render_markdown, summarize


class AccessMode(models.TextChoices):
    ALL = "all", "所有人"
    CAMPUS = "campus", "仅本校"
    RANGE = "range", "等级区间"


class Topic(models.Model):
    name = models.CharField("话题", max_length=40, unique=True)
    slug = models.SlugField(unique=True)
    description = models.CharField("介绍", max_length=200)
    icon = models.CharField("图标", max_length=20, default="sparkles")
    color = models.CharField("配色", max_length=15, default="green")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "话题"
        verbose_name_plural = "话题"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("forum:topic", args=[self.slug])


class PostQuerySet(models.QuerySet):
    def readable_by(self, user):
        if not user.is_authenticated or not user.is_verified:
            return self.filter(access_mode=AccessMode.ALL)
        same_campus = Education.objects.active().filter(
            user_id=OuterRef("author_id"), school_id__in=user.school_ids,
        )
        in_range = Education.objects.active().filter(
            user=user, school__tier_id__gte=OuterRef("read_min_tier_id"),
            school__tier_id__lte=OuterRef("read_max_tier_id"),
        )
        return self.annotate(_same_campus=Exists(same_campus), _in_read_range=Exists(in_range)).filter(
            Q(author=user) | Q(access_mode=AccessMode.ALL)
            | Q(access_mode=AccessMode.CAMPUS, _same_campus=True)
            | Q(access_mode=AccessMode.RANGE, _in_read_range=True)
        )

    def preferred_by(self, user):
        """首页偏好：只保留阅读范围完整覆盖偏好区间的帖子。"""
        if not user.is_authenticated or user.home_min_tier_id is None:
            return self
        return self.filter(
            Q(access_mode=AccessMode.ALL)
            | Q(access_mode=AccessMode.RANGE, read_min_tier_id__lte=user.home_min_tier_id, read_max_tier_id__gte=user.home_max_tier_id)
        )

    def with_activity(self, user):
        votes = PostVote.objects.filter(post_id=OuterRef("pk"))
        comments = Comment.objects.filter(post_id=OuterRef("pk"), is_deleted=False)
        posts = self.select_related("author", "topic", "read_min_tier", "read_max_tier", "reply_min_tier", "reply_max_tier").prefetch_related(
            Prefetch("author__educations", queryset=Education.objects.active().select_related("school__tier"), to_attr="_active_educations")
        ).annotate(
            score=Coalesce(Subquery(votes.values("post_id").annotate(total=Sum("value")).values("total")), 0),
            comment_count=Coalesce(Subquery(comments.values("post_id").annotate(total=Count("id")).values("total")), 0),
        )
        if user.is_authenticated:
            return posts.annotate(
                viewer_vote=Coalesce(Subquery(votes.filter(user=user).values("value")[:1]), 0),
                viewer_saved=Exists(SavedPost.objects.filter(user=user, post_id=OuterRef("pk"))),
            )
        return posts.annotate(viewer_vote=Value(0, output_field=IntegerField()), viewer_saved=Value(False))

    def cards(self, user):
        """列表卡片：可读帖子与互动统计，只读摘要，不读取正文。"""
        return self.readable_by(user).with_activity(user).defer("body", "body_html")


class Rendered(models.Model):
    """正文保存时渲染一次 Markdown；页面直接输出清理过的 HTML，列表只用纯文本摘要。"""

    body_html = models.TextField(default="", editable=False)
    excerpt = models.CharField(max_length=200, default="", editable=False)

    class Meta:
        abstract = True

    def save(self, **kwargs):
        fields = kwargs.get("update_fields")
        if fields is None or "body" in fields:
            self.body_html = render_markdown(self.body)
            self.excerpt = summarize(self.body_html)
            if fields is not None:
                kwargs["update_fields"] = {*fields, "body_html", "excerpt"}
        super().save(**kwargs)

    @property
    def html(self):
        return mark_safe(self.body_html)


class Post(Rendered):
    class Kind(models.TextChoices):
        QUESTION = "question", "提问"
        DISCUSSION = "discussion", "讨论"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="posts")
    kind = models.CharField("类型", max_length=12, choices=Kind, default=Kind.DISCUSSION)
    title = models.CharField("标题", max_length=180)
    body = models.TextField("内容")
    access_mode = models.CharField("访问范围", max_length=8, choices=AccessMode, default=AccessMode.ALL)
    read_min_tier = models.ForeignKey("accounts.SchoolTier", null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="阅读最低等级")
    read_max_tier = models.ForeignKey("accounts.SchoolTier", null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="阅读最高等级")
    reply_min_tier = models.ForeignKey("accounts.SchoolTier", null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="回复最低等级")
    reply_max_tier = models.ForeignKey("accounts.SchoolTier", null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="回复最高等级")
    accepted_comment = models.ForeignKey("Comment", null=True, blank=True, on_delete=models.SET_NULL, related_name="accepted_for")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"]), models.Index(fields=["topic", "-created_at"])]
        constraints = [models.CheckConstraint(
            condition=(
                Q(access_mode__in=[AccessMode.ALL, AccessMode.CAMPUS], read_min_tier__isnull=True, read_max_tier__isnull=True, reply_min_tier__isnull=True, reply_max_tier__isnull=True)
                | Q(access_mode=AccessMode.RANGE, read_min_tier__isnull=False, read_max_tier__isnull=False, reply_min_tier__isnull=False, reply_max_tier__isnull=False,
                    read_min_tier__lte=F("reply_min_tier"), reply_min_tier__lte=F("reply_max_tier"), reply_max_tier__lte=F("read_max_tier"))
            ), name="valid_post_tier_intervals",
        )]
        verbose_name = "帖子"
        verbose_name_plural = "帖子"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("forum:detail", args=[self.pk])

    def can_reply(self, user):
        """帖子须经 readable_by 取得；这里只判断回复范围。"""
        if not user.is_authenticated or not user.is_verified:
            return False
        return self.access_mode != AccessMode.RANGE or any(
            self.reply_min_tier_id <= rank <= self.reply_max_tier_id for rank in user.school_tier_ranks
        )

    @property
    def access_label(self):
        if self.access_mode == AccessMode.RANGE:
            return f"{self.read_min_tier.name} — {self.read_max_tier.name}"
        return self.get_access_mode_display()


class Comment(Rendered):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    body = models.TextField("回复")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "回复"
        verbose_name_plural = "回复"


class PostVote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="votes")
    value = models.SmallIntegerField(choices=[(1, "赞同"), (-1, "不赞同")])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="unique_post_vote"),
            models.CheckConstraint(condition=Q(value__in=[-1, 1]), name="valid_post_vote"),
        ]


class CommentVote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="votes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "comment"], name="unique_comment_vote")]


class SavedPost(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_posts")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="unique_saved_post")]


class TopicFollow(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="followers")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "topic"], name="unique_topic_follow")]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_notifications")
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=[("reply", "回复了你的讨论"), ("accepted", "采纳了你的回答")], default="reply")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "通知"
        verbose_name_plural = "通知"
