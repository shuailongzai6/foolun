from .models import Notification, Post, Topic


def navigation(request):
    unread = 0
    if request.user.is_authenticated:
        unread = Notification.objects.filter(recipient=request.user, is_read=False, post__in=Post.objects.readable_by(request.user)).count()
    return {"nav_topics": Topic.objects.all(), "unread_notifications": unread}
