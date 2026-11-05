from django.core.management.base import BaseCommand
from django.db import transaction

from network.models import Post, User

DEMO_PASSWORD = "demo-pass-12345"

DEMO_POSTS = {
    "alice": [
        "Hello, Network! This is my first post.",
        "Just finished reading about Django's ORM. Many-to-many relations are neat.",
        "Coffee first, code second.",
    ],
    "bob": [
        "Shipping a small feature today. Wish me luck!",
        "Unpopular opinion: tabs vs spaces matters less than having a formatter.",
    ],
    "carol": [
        "Learning fetch() and async/await, and it finally clicked.",
    ],
}

DEMO_FOLLOWS = {"alice": ["bob", "carol"], "bob": ["alice"], "carol": ["alice"]}


class Command(BaseCommand):
    help = "Create demo users, posts, follows and likes for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        users = {}
        for username in DEMO_POSTS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[username] = user

        for username, contents in DEMO_POSTS.items():
            for content in contents:
                Post.objects.get_or_create(author=users[username], content=content)

        for follower, targets in DEMO_FOLLOWS.items():
            users[follower].following.add(*[users[t] for t in targets])

        for post in Post.objects.exclude(author=users["alice"]):
            post.likes.add(users["alice"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready. Log in as alice, bob or carol with password '{DEMO_PASSWORD}'."
            )
        )
