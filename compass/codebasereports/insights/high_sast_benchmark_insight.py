from django.db.models import F

from mvp.models import ReferenceRecord

from .warnings_benchmark_insight import WarningsBenchmarkInsight


class HighSastBenchmarkInsight(WarningsBenchmarkInsight):
    def get_reference_records(self):
        return (
            ReferenceRecord.objects.all()
            .order_by("code_high_risk")
            .only("code_high_risk")
            .values("code_high_risk")
            .annotate(value=F("code_high_risk"))
        )
