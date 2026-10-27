from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_htmx.http import HttpResponseClientRedirect, trigger_client_event

from accounts.models import Education

from .forms import CommentForm, PostForm, VoteForm
from .models import Comment, CommentVote, Notification, Post, PostVote, SavedPost, Topic, TopicFollow
from .text import render_markdown


def verified_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            destination = request.headers.get("HX-Current-URL", request.get_full_path())
            response = redirect_to_login(destination)
        elif not request.user.is_verified:
            messages.info(request, "绑定一份学历后，就可以参与讨论了。")
            response = redirect("accounts:certification")
        else:
            return view(request, *args, **kwargs)
        return HttpResponseClientRedirect(response.url) if request.htmx else response
    return wrapped


def accessible_post(request, pk):
    return get_object_or_404(
        Post.objects.readable_by(request.user).with_activity(request.user), pk=pk
    )


def return_to(request, fallback):
    target = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def page(request, items, size=12):
    return Paginator(items, size).get_page(request.GET.get("page"))


def comment_threads(post, user, sort):
    """一级回复按所选方式排序；楼中楼按时间平铺在所属一级回复下。"""
    comments = list(post.comments.select_related("author", "parent__author").prefetch_related(
        Prefetch("author__educations", queryset=Education.objects.active().select_related("school__tier"), to_attr="_active_educations")
    ).annotate(like_count=Count("votes")))
    liked = set(CommentVote.objects.filter(user=user, comment__post=post).values_list("comment_id", flat=True)) if user.is_authenticated else set()
    answered = {comment.parent_id for comment in comments}
    roots, root_of = [], {}
    for comment in comments:
        comment.viewer_liked = comment.pk in liked
        comment.has_replies = comment.pk in answered
        comment.thread = []
        root = root_of.get(comment.parent_id)
        root_of[comment.pk] = root or comment
        (root.thread if root else roots).append(comment)
    if sort == "best":
        roots.sort(key=lambda comment: (comment.pk != post.accepted_comment_id, -comment.like_count, comment.created_at))
    return roots


def discussion(request, post, form=None, **extra):
    sort = "new" if request.GET.get("sort", request.POST.get("sort")) == "new" else "best"
    return {
        "post": post, "sort": sort, "comments": comment_threads(post, request.user, sort),
        "can_reply": post.can_reply(request.user), "comment_form": form or CommentForm(post=post), **extra,
    }


def discussion_update(request, post, form=None, message=None, **extra):
    """HTMX 局部刷新讨论区，并顺带更新帖子操作栏里的回复数。"""
    post = accessible_post(request, post.pk)
    response = render(request, "forum/partials/discussion.html", discussion(request, post, form, oob=True, **extra))
    return trigger_client_event(response, "toast", {"message": message}) if message else response


def post_actions(request, pk):
    return render(request, "forum/partials/post_actions.html", {"post": accessible_post(request, pk), "next_url": request.POST.get("next", "")})


def home(request):
    tab = request.GET.get("tab")
    tab = tab if tab in ("following", "campus") else "discover"
    if tab != "discover" and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    posts = Post.objects.cards(request.user).preferred_by(request.user)
    followed = None
    if tab == "following":
        followed = Topic.objects.filter(followers__user=request.user)
        posts = posts.filter(topic__in=followed)
    elif tab == "campus":
        authors = Education.objects.active().filter(school_id__in=request.user.school_ids).values("user_id")
        posts = posts.filter(author_id__in=authors)
    sort = "new" if request.GET.get("sort") == "new" else "hot"
    posts = posts.order_by("-created_at") if sort == "new" else posts.order_by("-score", "-comment_count", "-created_at")
    return render(request, "forum/home.html", {"page_obj": page(request, posts), "tab": tab, "sort": sort, "followed_topics": followed})


def search(request):
    query = request.GET.get("q", "").strip()[:200]
    posts = Post.objects.cards(request.user)
    posts = posts.filter(Q(title__icontains=query) | Q(body__icontains=query) | Q(topic__name__icontains=query)) if query else posts.none()
    return render(request, "forum/search.html", {"q": query, "page_obj": page(request, posts)})


def topics(request):
    visible = Post.objects.readable_by(request.user)
    items = Topic.objects.annotate(post_count=Count("posts", filter=Q(posts__in=visible)))
    if request.user.is_authenticated:
        items = items.annotate(viewer_followed=Exists(TopicFollow.objects.filter(user=request.user, topic_id=OuterRef("pk"))))
    return render(request, "forum/topics.html", {"topics": items})


def topic(request, slug):
    item = get_object_or_404(Topic, slug=slug)
    posts = Post.objects.cards(request.user).filter(topic=item)
    followed = request.user.is_authenticated and TopicFollow.objects.filter(user=request.user, topic=item).exists()
    return render(request, "forum/topic.html", {"topic": item, "followed": followed, "page_obj": page(request, posts)})


def detail(request, pk):
    post = accessible_post(request, pk)
    related = Post.objects.cards(request.user).filter(topic=post.topic).exclude(pk=post.pk)[:5]
    return render(request, "forum/detail.html", discussion(request, post, related_posts=related))


@verified_required
def compose(request, pk=None):
    post = get_object_or_404(Post, pk=pk, author=request.user) if pk else None
    form = PostForm(request.POST or None, instance=post, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            saved.author = request.user
            saved.save()
            form.save_m2m()
        messages.success(request, "修改已保存。" if post else "你的讨论已发布，期待校园里的新声音。")
        return redirect(saved)
    return render(request, "forum/compose.html", {
        "form": form, "post": post, "tiers": [{"rank": tier.pk, "name": tier.name} for tier in form.tiers], "own_ranks": form.own_ranks,
    })


@verified_required
@require_POST
def preview(request):
    return render(request, "forum/partials/preview.html", {"html": render_markdown(request.POST.get("body", "")[:20000])})


@verified_required
@require_POST
def comment(request, pk):
    post = accessible_post(request, pk)
    if not post.can_reply(request.user):
        raise PermissionDenied("作者未向你的学校开放回复权限。")
    form = CommentForm(request.POST, post=post)
    if not form.is_valid():
        if request.htmx:
            return discussion_update(request, post, form)
        messages.error(request, "回复未发布，请检查内容和回复对象。")
        return redirect(post)
    with transaction.atomic():
        reply = form.save(commit=False)
        reply.author, reply.post = request.user, post
        reply.save()
        Post.objects.filter(pk=post.pk).update(updated_at=timezone.now())
        recipients = {post.author_id}
        if reply.parent_id:
            recipients.add(reply.parent.author_id)
        Notification.objects.bulk_create([
            Notification(recipient_id=user_id, actor=request.user, post=post, comment=reply)
            for user_id in recipients - {request.user.pk}
        ])
    if request.htmx:
        return discussion_update(request, post, message="回复已发布。", highlight=reply.pk)
    return redirect(post.get_absolute_url() + f"#comment-{reply.pk}")


@verified_required
@require_POST
def vote(request, pk):
    post = accessible_post(request, pk)
    form = VoteForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("无效的投票。")
    value = int(form.cleaned_data["value"])
    with transaction.atomic():
        previous = PostVote.objects.filter(user=request.user, post=post).first()
        if previous and previous.value == value:
            previous.delete()
        else:
            PostVote.objects.update_or_create(user=request.user, post=post, defaults={"value": value})
    return post_actions(request, pk) if request.htmx else return_to(request, post)


@verified_required
@require_POST
def save(request, pk):
    post = accessible_post(request, pk)
    with transaction.atomic():
        item, created = SavedPost.objects.get_or_create(user=request.user, post=post)
        if not created:
            item.delete()
    return post_actions(request, pk) if request.htmx else return_to(request, post)


@verified_required
@require_POST
def like_comment(request, pk):
    item = get_object_or_404(Comment, pk=pk, is_deleted=False)
    post = accessible_post(request, item.post_id)
    with transaction.atomic():
        liked, created = CommentVote.objects.get_or_create(user=request.user, comment=item)
        if not created:
            liked.delete()
    if request.htmx:
        item.viewer_liked, item.like_count = created, item.votes.count()
        return render(request, "forum/partials/comment_like.html", {"comment": item})
    return redirect(post.get_absolute_url() + f"#comment-{item.pk}")


@verified_required
@require_POST
def accept_comment(request, pk):
    item = get_object_or_404(Comment, pk=pk, is_deleted=False, parent__isnull=True, post__author=request.user, post__kind=Post.Kind.QUESTION)
    post = item.post
    with transaction.atomic():
        post.accepted_comment = None if post.accepted_comment_id == item.pk else item
        post.save(update_fields=["accepted_comment", "updated_at"])
        if post.accepted_comment_id and item.author_id != request.user.pk:
            Notification.objects.create(recipient=item.author, actor=request.user, post=post, comment=item, kind="accepted")
    if request.htmx:
        return discussion_update(request, post, highlight=item.pk)
    return redirect(post.get_absolute_url() + f"#comment-{item.pk}")


@verified_required
@require_POST
def delete_comment(request, pk):
    item = get_object_or_404(Comment.objects.select_related("post"), pk=pk, author=request.user)
    with transaction.atomic():
        item.body, item.is_deleted = "", True
        item.save(update_fields=["body", "is_deleted"])
        Post.objects.filter(accepted_comment=item).update(accepted_comment=None)
    return discussion_update(request, item.post, message="回复已删除。") if request.htmx else redirect(item.post)


@verified_required
@require_POST
def delete_post(request, pk):
    post = get_object_or_404(Post, pk=pk, author=request.user)
    post.delete()
    messages.success(request, "帖子已删除。")
    return redirect("forum:home")


@login_required
def saved(request):
    posts = Post.objects.cards(request.user).filter(saved_by__user=request.user).order_by("-saved_by__created_at")
    return render(request, "forum/saved.html", {"page_obj": page(request, posts)})


@verified_required
@require_POST
def follow(request, slug):
    item = get_object_or_404(Topic, slug=slug)
    with transaction.atomic():
        connection, created = TopicFollow.objects.get_or_create(user=request.user, topic=item)
        if not created:
            connection.delete()
    if request.htmx:
        return render(request, "forum/partials/follow.html", {"topic": item, "followed": created})
    return return_to(request, item)


@login_required
def notifications(request):
    items = request.user.notifications.filter(post__in=Post.objects.readable_by(request.user)).select_related("actor", "post", "comment").defer(
        "post__body", "post__body_html", "comment__body", "comment__body_html"
    )
    if request.method == "POST":
        items.filter(is_read=False).update(is_read=True)
        return redirect("forum:notifications")
    return render(request, "forum/notifications.html", {"page_obj": page(request, items, 20)})


@login_required
@require_POST
def open_notification(request, pk):
    item = get_object_or_404(Notification, pk=pk, recipient=request.user, post__in=Post.objects.readable_by(request.user))
    item.is_read = True
    item.save(update_fields=["is_read"])
    anchor = f"#comment-{item.comment_id}" if item.comment_id else ""
    return redirect(item.post.get_absolute_url() + anchor)


def about(request):
    return render(request, "forum/about.html")
