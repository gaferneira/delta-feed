from datetime import timedelta

from django.db import migrations

LEGACY_BACKFILL_DAYS = 30


def set_legacy_cutoffs(apps, schema_editor):
    """Sources imported before the bounded backfill get a cutoff derived from creation.

    Their first import was unbounded, so every entry still in the feed is already
    stored; the cutoff only stops a later poll from treating deleted or rotated-out
    history as new. Sources never fetched keep NULL and receive a bounded backfill.
    """
    Source = apps.get_model("content", "Source")
    for source in Source.objects.filter(
        backfill_cutoff__isnull=True, last_fetch_at__isnull=False
    ):
        source.backfill_cutoff = source.created_at - timedelta(days=LEGACY_BACKFILL_DAYS)
        source.save(update_fields=["backfill_cutoff"])


class Migration(migrations.Migration):
    dependencies = [("content", "0005_source_backfill_cutoff")]

    operations = [migrations.RunPython(set_legacy_cutoffs, migrations.RunPython.noop)]
