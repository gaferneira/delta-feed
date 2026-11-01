from django.conf import settings
from django.db import models

from delta_feed.content.models import Article


class ReadState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_read_states",
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="read_states",
    )
    is_read = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "article"], name="unique_user_article_read_state"
            ),
        ]


class SaveState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_save_states",
    )
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="save_states",
    )
    is_saved = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "article"], name="unique_user_article_save_state"
            ),
        ]
