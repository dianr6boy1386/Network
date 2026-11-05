import json

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import POST_MAX_LENGTH, Post, User
from .views import POSTS_PER_PAGE

PASSWORD = "a-Strong-pass-123"

# Fast hasher keeps the suite quick; production uses Django's default (PBKDF2).
fast_hashing = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)


def make_user(username, **kwargs):
    return User.objects.create_user(username, f"{username}@example.com", PASSWORD, **kwargs)


@fast_hashing
class ModelTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")

    def test_toggle_follow(self):
        self.assertTrue(self.alice.toggle_follow(self.bob))
        self.assertIn(self.bob, self.alice.following.all())
        self.assertIn(self.alice, self.bob.followers.all())
        self.assertFalse(self.alice.toggle_follow(self.bob))
        self.assertEqual(self.alice.following.count(), 0)

    def test_follow_is_one_way(self):
        self.alice.toggle_follow(self.bob)
        self.assertEqual(self.bob.following.count(), 0)

    def test_cannot_follow_self(self):
        with self.assertRaises(ValueError):
            self.alice.toggle_follow(self.alice)

    def test_toggle_like(self):
        post = Post.objects.create(author=self.alice, content="hi")
        self.assertTrue(post.toggle_like(self.bob))
        self.assertEqual(post.likes.count(), 1)
        self.assertFalse(post.toggle_like(self.bob))
        self.assertEqual(post.likes.count(), 0)

    def test_posts_ordered_newest_first(self):
        first = Post.objects.create(author=self.alice, content="first")
        second = Post.objects.create(author=self.alice, content="second")
        self.assertEqual(list(Post.objects.all()), [second, first])

    def test_serialize(self):
        post = Post.objects.create(author=self.alice, content="hi")
        post.likes.add(self.bob)
        data = post.serialize(self.bob)
        self.assertEqual(data["author"], "alice")
        self.assertEqual(data["likes"], 1)
        self.assertTrue(data["liked"])
        self.assertFalse(post.serialize(self.alice)["liked"])


@fast_hashing
class AuthTests(TestCase):
    def test_register_logs_user_in(self):
        response = self.client.post(
            reverse("register"),
            {"username": "dana", "email": "d@example.com", "password": PASSWORD, "confirmation": PASSWORD},
        )
        self.assertRedirects(response, reverse("index"))
        self.assertTrue(User.objects.filter(username="dana").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_rejections(self):
        make_user("taken")
        cases = {
            "mismatch": ({"username": "x", "password": PASSWORD, "confirmation": "other"}, "must match"),
            "duplicate": ({"username": "taken", "password": PASSWORD, "confirmation": PASSWORD}, "already taken"),
            "blank": ({"username": "  ", "password": PASSWORD, "confirmation": PASSWORD}, "required"),
            "weak": ({"username": "weak", "password": "123", "confirmation": "123"}, "short"),
        }
        for name, (data, expected) in cases.items():
            with self.subTest(name):
                response = self.client.post(reverse("register"), data)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)

    def test_login_and_logout(self):
        make_user("alice")
        bad = self.client.post(reverse("login"), {"username": "alice", "password": "nope"})
        self.assertContains(bad, "Invalid username")
        good = self.client.post(reverse("login"), {"username": "alice", "password": PASSWORD})
        self.assertRedirects(good, reverse("index"))
        self.client.get(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_next_redirect_and_open_redirect_blocked(self):
        make_user("alice")
        ok = self.client.post(
            reverse("login"), {"username": "alice", "password": PASSWORD, "next": reverse("following")}
        )
        self.assertRedirects(ok, reverse("following"))
        self.client.get(reverse("logout"))
        evil = self.client.post(
            reverse("login"), {"username": "alice", "password": PASSWORD, "next": "https://evil.example/"}
        )
        self.assertRedirects(evil, reverse("index"))

    def test_following_requires_login(self):
        response = self.client.get(reverse("following"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('following')}")


@fast_hashing
class PageTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")

    def test_index_shows_posts_newest_first_with_details(self):
        Post.objects.create(author=self.alice, content="older post")
        Post.objects.create(author=self.bob, content="newer post")
        response = self.client.get(reverse("index"))
        self.assertEqual([p.content for p in response.context["posts"]], ["newer post", "older post"])
        self.assertContains(response, "likes: <span")
        self.assertNotContains(response, "New Post")  # anonymous: no compose box

    def test_create_post(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("index"), {"content": "  Hello world  "})
        self.assertRedirects(response, reverse("index"))
        post = Post.objects.get()
        self.assertEqual((post.author, post.content), (self.alice, "Hello world"))

    def test_create_post_validation(self):
        self.client.force_login(self.alice)
        for content in ["", "   ", "x" * (POST_MAX_LENGTH + 1)]:
            with self.subTest(length=len(content)):
                response = self.client.post(reverse("index"), {"content": content})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Post.objects.count(), 0)

    def test_anonymous_cannot_create_post(self):
        response = self.client.post(reverse("index"), {"content": "sneaky"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.count(), 0)

    def test_post_content_is_escaped(self):
        Post.objects.create(author=self.alice, content="<script>alert(1)</script>")
        response = self.client.get(reverse("index"))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_pagination(self):
        for i in range(POSTS_PER_PAGE + 5):
            Post.objects.create(author=self.alice, content=f"post {i}")
        page1 = self.client.get(reverse("index"))
        self.assertEqual(len(page1.context["posts"]), POSTS_PER_PAGE)
        self.assertContains(page1, "Next")
        self.assertNotContains(page1, "Previous")
        page2 = self.client.get(reverse("index"), {"page": 2})
        self.assertEqual(len(page2.context["posts"]), 5)
        self.assertContains(page2, "Previous")
        self.assertNotContains(page2, ">Next<")
        # Bad page numbers degrade gracefully
        self.assertEqual(self.client.get(reverse("index"), {"page": "abc"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("index"), {"page": 999}).status_code, 200)

    def test_no_pagination_for_single_page(self):
        Post.objects.create(author=self.alice, content="only one")
        self.assertNotContains(self.client.get(reverse("index")), "Page 1 of")

    def test_profile(self):
        Post.objects.create(author=self.alice, content="a1")
        Post.objects.create(author=self.bob, content="b1")
        self.bob.toggle_follow(self.alice)
        response = self.client.get(reverse("profile", args=["alice"]))
        self.assertEqual(response.context["followers_count"], 1)
        self.assertEqual(response.context["following_count"], 0)
        self.assertEqual([p.content for p in response.context["posts"]], ["a1"])
        self.assertNotContains(response, "follow-btn")  # anonymous: no button

    def test_profile_follow_button_rules(self):
        self.client.force_login(self.alice)
        self.assertContains(self.client.get(reverse("profile", args=["bob"])), "follow-btn")
        self.assertNotContains(self.client.get(reverse("profile", args=["alice"])), "follow-btn")

    def test_profile_404(self):
        self.assertEqual(self.client.get(reverse("profile", args=["ghost"])).status_code, 404)

    def test_following_feed_only_has_followed_authors(self):
        carol = make_user("carol")
        Post.objects.create(author=self.bob, content="from bob")
        Post.objects.create(author=carol, content="from carol")
        Post.objects.create(author=self.alice, content="from me")
        self.alice.toggle_follow(self.bob)
        self.client.force_login(self.alice)
        response = self.client.get(reverse("following"))
        self.assertEqual([p.content for p in response.context["posts"]], ["from bob"])

    def test_liked_state_rendered_for_user(self):
        post = Post.objects.create(author=self.alice, content="p")
        post.likes.add(self.bob)
        self.client.force_login(self.bob)
        posts = self.client.get(reverse("index")).context["posts"]
        self.assertTrue(posts[0].liked_by_user)
        self.assertEqual(posts[0].like_count, 1)

    def test_edit_button_only_for_author(self):
        Post.objects.create(author=self.alice, content="p")
        self.client.force_login(self.bob)
        self.assertNotContains(self.client.get(reverse("index")), "edit-btn")
        self.client.force_login(self.alice)
        self.assertContains(self.client.get(reverse("index")), "edit-btn")


@fast_hashing
class ApiTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.post = Post.objects.create(author=self.alice, content="original")
        self.edit_url = reverse("post_detail", args=[self.post.pk])
        self.like_url = reverse("toggle_like", args=[self.post.pk])

    def put(self, url, payload, **kw):
        body = payload if isinstance(payload, str) else json.dumps(payload)
        return self.client.put(url, body, content_type="application/json", **kw)

    # edit
    def test_author_can_edit(self):
        self.client.force_login(self.alice)
        response = self.put(self.edit_url, {"content": "  updated  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "updated")
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "updated")

    def test_cannot_edit_someone_elses_post(self):
        self.client.force_login(self.bob)
        response = self.put(self.edit_url, {"content": "hacked"})
        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "original")

    def test_edit_requires_authentication(self):
        self.assertEqual(self.put(self.edit_url, {"content": "x"}).status_code, 401)

    def test_edit_validation(self):
        self.client.force_login(self.alice)
        bad_payloads = [{"content": ""}, {"content": "  "}, {"content": "x" * (POST_MAX_LENGTH + 1)},
                        {"content": 5}, {"nope": 1}, [1, 2], "not json"]
        for payload in bad_payloads:
            with self.subTest(payload=str(payload)[:30]):
                self.assertEqual(self.put(self.edit_url, payload).status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "original")

    def test_edit_missing_post(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.put(reverse("post_detail", args=[9999]), {"content": "x"}).status_code, 404)

    def test_edit_rejects_other_methods(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(self.edit_url, {}).status_code, 405)
        self.assertEqual(self.client.get(self.edit_url).status_code, 405)

    # like
    def test_like_and_unlike(self):
        self.client.force_login(self.bob)
        first = self.client.post(self.like_url)
        self.assertEqual(first.json(), {"liked": True, "likes": 1})
        second = self.client.post(self.like_url)
        self.assertEqual(second.json(), {"liked": False, "likes": 0})

    def test_like_requires_authentication_and_post(self):
        self.assertEqual(self.client.post(self.like_url).status_code, 401)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(reverse("toggle_like", args=[9999])).status_code, 404)
        self.assertEqual(self.client.get(self.like_url).status_code, 405)

    # follow
    def test_follow_and_unfollow(self):
        self.client.force_login(self.bob)
        url = reverse("toggle_follow", args=["alice"])
        self.assertEqual(self.client.post(url).json(), {"following": True, "followers": 1})
        self.assertEqual(self.client.post(url).json(), {"following": False, "followers": 0})

    def test_cannot_follow_self_via_api(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("toggle_follow", args=["alice"]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.alice.following.count(), 0)

    def test_follow_requires_authentication_and_user(self):
        self.assertEqual(self.client.post(reverse("toggle_follow", args=["alice"])).status_code, 401)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(reverse("toggle_follow", args=["ghost"])).status_code, 404)

    # csrf
    def test_api_enforces_csrf(self):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(self.bob)
        self.assertEqual(client.post(self.like_url).status_code, 403)


@fast_hashing
class SeedCommandTests(TestCase):
    def test_seed_demo_is_idempotent(self):
        call_command("seed_demo", verbosity=0)
        users, posts = User.objects.count(), Post.objects.count()
        call_command("seed_demo", verbosity=0)
        self.assertEqual((User.objects.count(), Post.objects.count()), (users, posts))
        self.assertTrue(User.objects.get(username="alice").following.exists())
