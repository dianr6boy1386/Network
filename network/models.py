from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxLengthValidator
from django.db import models

POST_MAX_LENGTH = 500


class User(AbstractUser):
    """A registered user. Following is a one-way, self-referential relation."""

    following = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="followers",
        blank=True,
    )

    def toggle_follow(self, other):
        """Follow `other` if not already following, otherwise unfollow.

        Returns True if the user is following `other` afterwards.
        Raises ValueError if a user tries to follow themselves.
        """
        if other.pk == self.pk:
            raise ValueError("Users cannot follow themselves.")
        if self.following.filter(pk=other.pk).exists():
            self.following.remove(other)
            return False
        self.following.add(other)
        return True


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(validators=[MaxLengthValidator(POST_MAX_LENGTH)])
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    likes = models.ManyToManyField(User, related_name="liked_posts", blank=True)

    class Meta:
        ordering = ["-timestamp", "-id"]

    def __str__(self):
        return f"Post {self.pk} by {self.author.username}"

    def toggle_like(self, user):
        """Like the post if `user` has not liked it yet, otherwise unlike it.

        Returns True if the post is liked by `user` afterwards.
        """
        if self.likes.filter(pk=user.pk).exists():
            self.likes.remove(user)
            return False
        self.likes.add(user)
        return True

    def serialize(self, user=None):
        return {
            "id": self.pk,
            "author": self.author.username,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "likes": self.likes.count(),
            "liked": bool(
                user is not None
                and user.is_authenticated
                and self.likes.filter(pk=user.pk).exists()
            ),
        }
