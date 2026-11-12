from django.core.management.base import BaseCommand

from delta_feed.analysis.use_cases import (
    enqueue_compare_group,
    enqueue_compare_run,
    runs_awaiting_comparison,
)
from delta_feed.knowledge.models import ExtractedMention


class Command(BaseCommand):
    help = (
        "Queue comparison for completed extraction runs and resolved mention groups "
        "that were not compared yet, so earlier articles reach the baseline."
    )

    def handle(self, *args, **options):
        runs = 0
        for run_id in runs_awaiting_comparison().order_by("id").values_list("pk", flat=True):
            runs += enqueue_compare_run(run_id) is not None
        groups = set()
        waiting = ExtractedMention.objects.filter(
            status=ExtractedMention.Status.RESOLVED, compared_at__isnull=True
        ).order_by("analysis_run_id", "id")
        for mention in waiting:
            groups.add(
                (
                    mention.normalized_name,
                    mention.entity_type.strip().casefold(),
                    mention.analysis_run_id,
                )
            )
        jobs = 0
        for normalized_name, entity_type, run_id in sorted(groups, key=lambda g: (g[2], g[0], g[1])):
            jobs += enqueue_compare_group(normalized_name, entity_type, run_id) is not None
        self.stdout.write(f"Queued {runs} run comparison(s) and {jobs} mention group(s).")
