from django import forms

from .models import POST_MAX_LENGTH, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "maxlength": POST_MAX_LENGTH,
                    "placeholder": "What's on your mind?",
                    "aria-label": "Post content",
                }
            )
        }
        error_messages = {
            "content": {"required": "A post cannot be empty."},
        }
