from django.db.models import OuterRef

from delta_feed.analysis.models import AnalysisRun


def current_run(**filters):
    """Extraction runs of the outer article's current revision (use inside a subquery)."""
    return AnalysisRun.objects.filter(
        source_article=OuterRef("pk"),
        article_revision__version=OuterRef("current_version"),
        kind=AnalysisRun.Kind.EXTRACT,
        **filters,
    )


def analysis_status(row) -> str:
    if row["is_analysed"]:
        return "analysed"
    return "failed" if row["is_analysis_failed"] else "unanalysed"
