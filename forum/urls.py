from django.urls import path

from . import views

app_name = "forum"
urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("topics/", views.topics, name="topics"),
    path("topics/<slug:slug>/", views.topic, name="topic"),
    path("topics/<slug:slug>/follow/", views.follow, name="follow"),
    path("new/", views.compose, name="compose"),
    path("preview/", views.preview, name="preview"),
    path("posts/<int:pk>/", views.detail, name="detail"),
    path("posts/<int:pk>/edit/", views.compose, name="edit"),
    path("posts/<int:pk>/delete/", views.delete_post, name="delete"),
    path("posts/<int:pk>/reply/", views.comment, name="comment"),
    path("posts/<int:pk>/vote/", views.vote, name="vote"),
    path("posts/<int:pk>/save/", views.save, name="save"),
    path("comments/<int:pk>/like/", views.like_comment, name="like_comment"),
    path("comments/<int:pk>/accept/", views.accept_comment, name="accept_comment"),
    path("comments/<int:pk>/delete/", views.delete_comment, name="delete_comment"),
    path("saved/", views.saved, name="saved"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/<int:pk>/open/", views.open_notification, name="open_notification"),
    path("about/", views.about, name="about"),
]
