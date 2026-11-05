from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Post, User


@admin.register(User)
class NetworkUserAdmin(UserAdmin):
    filter_horizontal = UserAdmin.filter_horizontal + ("following",)
    fieldsets = UserAdmin.fieldsets + (("Social", {"fields": ("following",)}),)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "short_content", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("content", "author__username")
    raw_id_fields = ("author", "likes")

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:60]
