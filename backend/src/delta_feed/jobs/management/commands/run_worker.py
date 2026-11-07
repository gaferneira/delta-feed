import time

from django.core.management.base import BaseCommand

from delta_feed.analysis.use_cases import schedule_due_analysis
from delta_feed.content.use_cases import schedule_due_polls
from delta_feed.jobs.services import claim_job, execute_claimed_job

SCHEDULE_CHECK_SECONDS = 60


class Command(BaseCommand):
    help = "Poll the database-backed job queue and execute allowlisted handlers."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run currently due work and exit.")
        parser.add_argument("--poll-interval", type=float, default=1.0)
        parser.add_argument("--max-jobs", type=int, default=0, help="Exit after this many claims (0 means unlimited).")

    def handle(self, *args, **options):
        interval = max(0.1, options["poll_interval"])
        max_jobs = max(0, options["max_jobs"])
        processed = 0
        next_schedule = 0.0
        while True:
            # Recurring polls and extraction are scheduled by the worker itself, at most once a minute.
            if time.monotonic() >= next_schedule:
                scheduled = schedule_due_polls()
                if scheduled:
                    self.stdout.write(f"Scheduled RSS polls for {len(scheduled)} source(s).")
                queued = schedule_due_analysis()
                if queued:
                    self.stdout.write(f"Queued extraction for {len(queued)} article(s).")
                next_schedule = time.monotonic() + SCHEDULE_CHECK_SECONDS
            job = claim_job()
            if job is not None:
                execute_claimed_job(job)
                processed += 1
                if max_jobs and processed >= max_jobs:
                    return
                continue
            if options["once"]:
                return
            time.sleep(interval)
