from .models import Notification, Post, Topic

SECTIONS = {"topics": "topics", "topic": "topics", "notifications": "notifications", "saved": "me", "settings": "me", "certification": "me", "password": "me"}


def navigation(request):
    match, user = request.resolver_match, request.user
    name = match.url_name if match else ""
    section = SECTIONS.get(name, "")
    if name == "home":
        section = "campus" if request.GET.get("tab") == "campus" else "home"
    elif name == "profile" and match.kwargs["username"] == user.get_username():
        section = "me"
    unread = 0
    if user.is_authenticated:
        unread = Notification.objects.filter(recipient=user, is_read=False, post__in=Post.objects.readable_by(user)).count()
    return {"nav_topics": Topic.objects.all(), "nav_section": section, "unread_notifications": unread}
