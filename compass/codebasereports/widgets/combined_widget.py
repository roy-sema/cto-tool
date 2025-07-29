from compass.codebasereports.widgets import ChartWidget
from mvp.models import ReferenceRecord


class CombinedWidget(ChartWidget):
    def get_widgets(self, widgets_data):
        sast_issues = widgets_data.get("snyk_high_sast_issues")
        insight_files = widgets_data.get("insight_files")

        warning_vs_development_chart = (
            self.get_warning_vs_development_chart(sast_issues, insight_files["rate"])
            if sast_issues is not None and insight_files is not None
            else None
        )

        return {"chart_warning_vs_development": warning_vs_development_chart}

    def get_warning_vs_development_chart(self, current_issues, current_development_rate):
        series = []

        reference_records = ReferenceRecord.objects.only("code_medium_risk", "development_activity_change_rate").values(
            "code_medium_risk", "development_activity_change_rate"
        )

        # use a set to avoid duplicate data points
        reference_points = set()
        for record in reference_records:
            x = record["development_activity_change_rate"]
            y = record["code_medium_risk"]

            # skip 0,0 data points as they don't add information
            if x or y:
                reference_points.add((x, y))

        series.append({"name": "Reference", "data": list(reference_points)})
        series.append(
            {
                "name": "Current project",
                "data": [(current_development_rate, current_issues)],
            }
        )

        return {"series": series} if series else None
