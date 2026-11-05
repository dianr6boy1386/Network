import json
from functools import wraps

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import PostForm
from .models import POST_MAX_LENGTH, Post, User

POSTS_PER_PAGE = 10


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _post_queryset():
    """Posts with their author and like count, newest first."""
    # Explicit ordering: aggregate queries (GROUP BY) ignore Meta.ordering.
    return (
        Post.objects.select_related("author")
        .annotate(like_count=Count("likes"))
        .order_by("-timestamp", "-id")
    )


def _paginate(request, queryset):
    """Return (page_obj, posts) for the requested page of `queryset`.

    Each post gets a `liked_by_user` flag, computed with a single query.
    Invalid or out-of-range page numbers fall back to a valid page.
    """
    page_obj = Paginator(queryset, POSTS_PER_PAGE).get_page(request.GET.get("page"))
    posts = list(page_obj.object_list)
    liked_ids = set()
    if request.user.is_authenticated and posts:
        liked_ids = set(
            request.user.liked_posts.filter(pk__in=[p.pk for p in posts]).values_list(
                "pk", flat=True
            )
        )
    for post in posts:
        post.liked_by_user = post.pk in liked_ids
    return page_obj, posts


def _json_error(message, status):
    return JsonResponse({"error": message}, status=status)


def api_login_required(view):
    """Like `login_required`, but answers API clients with JSON instead of a redirect."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _json_error("Authentication required.", 401)
        return view(request, *args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def index(request):
    """All posts, newest first. Authenticated users can also create a post here."""
    form = PostForm()
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={reverse('index')}")
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return HttpResponseRedirect(reverse("index"))

    page_obj, posts = _paginate(request, _post_queryset())
    return render(
        request,
        "network/index.html",
        {
            "form": form,
            "page_obj": page_obj,
            "posts": posts,
            "max_length": POST_MAX_LENGTH,
        },
        status=400 if form.errors else 200,
    )


@login_required
def following(request):
    """Posts written by the users the current user follows."""
    queryset = _post_queryset().filter(author__in=request.user.following.all())
    page_obj, posts = _paginate(request, queryset)
    return render(
        request,
        "network/following.html",
        {"page_obj": page_obj, "posts": posts, "max_length": POST_MAX_LENGTH},
    )


def profile(request, username):
    """A user's profile: follower counts, follow button and their posts."""
    profile_user = get_object_or_404(User, username=username)
    page_obj, posts = _paginate(request, _post_queryset().filter(author=profile_user))
    is_own_profile = request.user.is_authenticated and request.user.pk == profile_user.pk
    is_following = (
        request.user.is_authenticated
        and not is_own_profile
        and request.user.following.filter(pk=profile_user.pk).exists()
    )
    return render(
        request,
        "network/profile.html",
        {
            "profile_user": profile_user,
            "followers_count": profile_user.followers.count(),
            "following_count": profile_user.following.count(),
            "is_own_profile": is_own_profile,
            "is_following": is_following,
            "page_obj": page_obj,
            "posts": posts,
            "max_length": POST_MAX_LENGTH,
        },
    )


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
def _safe_next_url(request):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return ""


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return HttpResponseRedirect(_safe_next_url(request) or reverse("index"))
        return render(
            request,
            "network/login.html",
            {"message": "Invalid username and/or password.", "next": _safe_next_url(request)},
        )
    return render(request, "network/login.html", {"next": _safe_next_url(request)})


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method != "POST":
        return render(request, "network/register.html")

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    confirmation = request.POST.get("confirmation", "")

    def error(message):
        return render(request, "network/register.html", {"message": message})

    if not username:
        return error("Username is required.")
    if password != confirmation:
        return error("Passwords must match.")
    try:
        validate_password(password, User(username=username, email=email))
    except ValidationError as exc:
        return error(" ".join(exc.messages))

    try:
        user = User.objects.create_user(username, email, password)
    except IntegrityError:
        return error("Username already taken.")
    login(request, user)
    return HttpResponseRedirect(reverse("index"))


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
@require_http_methods(["PUT"])
@api_login_required
def post_detail(request, post_id):
    """Edit the content of one of the current user's own posts."""
    try:
        post = Post.objects.select_related("author").get(pk=post_id)
    except Post.DoesNotExist:
        return _json_error("Post not found.", 404)

    # Authorisation: users may only ever edit their own posts.
    if post.author_id != request.user.pk:
        return _json_error("You can only edit your own posts.", 403)

    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return _json_error("Invalid JSON.", 400)
    if not isinstance(data, dict) or not isinstance(data.get("content"), str):
        return _json_error('Expected a JSON object with a string "content".', 400)

    form = PostForm({"content": data["content"]}, instance=post)
    if not form.is_valid():
        return _json_error(form.errors["content"][0], 400)
    form.save()
    return JsonResponse(post.serialize(request.user))


@require_POST
@api_login_required
def toggle_like(request, post_id):
    """Like or unlike a post. Returns the new like state and count."""
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return _json_error("Post not found.", 404)
    liked = post.toggle_like(request.user)
    return JsonResponse({"liked": liked, "likes": post.likes.count()})


@require_POST
@api_login_required
def toggle_follow(request, username):
    """Follow or unfollow a user. Returns the new state and follower count."""
    try:
        target = User.objects.get(username=username)
    except User.DoesNotExist:
        return _json_error("User not found.", 404)
    try:
        is_following = request.user.toggle_follow(target)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return JsonResponse(
        {"following": is_following, "followers": target.followers.count()}
    )
