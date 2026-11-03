from django.conf import settings
from django.db import migrations
from django.utils import timezone


def mark_existing_users_complete(apps, schema_editor):
    """Accounts that predate onboarding must not be trapped on /onboarding."""
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    user_model = apps.get_model(app_label, model_name)
    profile_model = apps.get_model("accounts", "ReaderProfile")
    now = timezone.now()
    for user_id in user_model.objects.values_list("pk", flat=True):
        profile_model.objects.update_or_create(
            user_id=user_id, defaults={"onboarding_completed_at": now}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_readerprofile_topicselection"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(mark_existing_users_complete, migrations.RunPython.noop),
    ]
