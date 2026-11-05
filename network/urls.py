from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("following", views.following, name="following"),
    path("profile/<str:username>", views.profile, name="profile"),
    # JSON API used by static/network/network.js
    path("api/posts/<int:post_id>", views.post_detail, name="post_detail"),
    path("api/posts/<int:post_id>/like", views.toggle_like, name="toggle_like"),
    path("api/users/<str:username>/follow", views.toggle_follow, name="toggle_follow"),
]
