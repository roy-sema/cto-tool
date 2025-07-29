from django.db.models import F

from mvp.models import ReferenceRecord

from .warnings_benchmark_insight import WarningsBenchmarkInsight


class HighCveBenchmarkInsight(WarningsBenchmarkInsight):
    def get_reference_records(self):
        return (
            ReferenceRecord.objects.all()
            .order_by("cve_high_risk")
            .only("cve_high_risk")
            .values("cve_high_risk")
            .annotate(value=F("cve_high_risk"))
        )
