from django.db import migrations


def link_runs_to_revisions(apps, schema_editor):
    """Best-effort link of legacy runs to the revision matching the article's current version.

    Runs whose article has no matching revision stay NULL; claims cannot be
    recorded against them (their evidence cannot be verified).
    """
    AnalysisRun = apps.get_model("analysis", "AnalysisRun")
    ArticleRevision = apps.get_model("content", "ArticleRevision")
    for run in AnalysisRun.objects.filter(article_revision__isnull=True).select_related(
        "source_article"
    ):
        revision = ArticleRevision.objects.filter(
            article_id=run.source_article_id,
            version=run.source_article.current_version,
        ).first()
        if revision is not None:
            AnalysisRun.objects.filter(pk=run.pk).update(article_revision=revision)


class Migration(migrations.Migration):
    dependencies = [
        ("analysis", "0003_analysisrun_article_revision"),
    ]

    operations = [
        migrations.RunPython(link_runs_to_revisions, migrations.RunPython.noop),
    ]
