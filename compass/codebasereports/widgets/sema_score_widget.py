from datetime import timedelta

from compass.codebasereports.widgets import ChartWidget
from mvp.models import ScoreRecord
from mvp.utils import get_tz_date


class SemaScoreWidget(ChartWidget):
    FIELD_COMPLIANCE = "compliance_score"
    FIELD_PRODUCT = "product_score"
    FIELD_SEMA = "sema_score"

    SCORE_FIELDS = [FIELD_COMPLIANCE, FIELD_PRODUCT, FIELD_SEMA]

    @property
    def score_level_conditions(self):
        return [
            (lambda r: r <= 15, ("Initial", "red")),
            (lambda r: 16 <= r < 30, ("Emerging", "orange")),
            (lambda r: 31 <= r <= 70, ("Mature", "yellow")),
            (lambda r: r >= 71, ("Advanced", "green")),
        ]

    def get_widgets(self, since, until):
        chart_score, chart_product_score, chart_compliance_score = self.get_charts(
            get_tz_date(since), get_tz_date(until)
        )

        return {
            "chart_sema_score": chart_score,
            "chart_sema_product_score": chart_product_score,
            "chart_sema_compliance_score": chart_compliance_score,
            **self.get_scores(),
        }

    def get_charts(self, since, until):
        # include last day's data
        until_date = until + timedelta(days=1)

        aggregate = self.AGGREGATE_DATE_FORMAT_WEEK if (until - since).days > self.AGGREGATE_WEEK_THRESHOLD else None

        records = self.get_records(since, until_date)

        charts = self.get_stacked_charts(
            records,
            since,
            until,
            fill_gaps=True,
            aggregate=aggregate,
            aggregate_strategy=self.AGGREGATE_STRATEGY_LATEST,
        )

        empty_chart = self.generate_no_data_chart(since, until_date, aggregate=aggregate)

        chart_score = charts.get(self.FIELD_SEMA, None) or empty_chart
        chart_product_score = charts.get(self.FIELD_PRODUCT, None) or empty_chart
        chart_compliance_score = charts.get(self.FIELD_COMPLIANCE, None) or empty_chart

        return chart_score, chart_product_score, chart_compliance_score

    def get_score(self, chart, last_week=False):
        if not chart or chart.get("no_data"):
            return None

        data = chart["series"][0]["data"]
        days = 8 if last_week else 1
        if len(data) < days:
            return None

        score = data[-days]
        phase, color = self.get_score_level(score)
        return (
            {
                "score": score,
                "color": color,
                "phase": phase,
            }
            if score is not None
            else None
        )

    def get_score_level(self, score):
        for condition, (phase, color) in self.score_level_conditions:
            if condition(score):
                return phase, color

        raise ValueError(f"Score {score} doesn't match any condition.")

    def get_records(self, since, until):
        rows = (
            ScoreRecord.objects.filter(
                organization=self.organization,
                date_time__gte=since,
                date_time__lt=until,
            )
            .order_by("date_time")
            .values(*self.SCORE_FIELDS, "date_time")
        )

        records = []
        for row in rows:
            for field in self.SCORE_FIELDS:
                if row[field] is None:
                    continue

                records.append(
                    {
                        "date_time": row["date_time"],
                        "field__name": field,
                        "project__name": field.replace("_", " ").title(),
                        "value": row[field],
                    }
                )

        return records

    def get_old_records(self, field_names):
        since, until = self.get_since_until(self.DAYS_MONTH)
        since_3_months, until = self.get_since_until(self.DAYS_MONTH * (self.OLD_RECORDS_MONTHS + 1))
        return self.get_records(since_3_months, since)

    def get_scores(self):
        since, until = self.get_since_until(self.DAYS_WEEK + 1)
        chart_score, chart_product_score, chart_compliance_score = self.get_charts(since, until)
        sema_score = self.get_score(chart_score)
        sema_score_last_week = self.get_score(chart_score, last_week=True)
        sema_score_diff = (
            sema_score["score"] - sema_score_last_week["score"] if sema_score and sema_score_last_week else None
        )

        return {
            "sema_score": sema_score,
            "sema_score_last_week": sema_score_last_week,
            "sema_score_diff": sema_score_diff,
            "sema_product_score": self.get_score(chart_product_score),
            "sema_compliance_score": self.get_score(chart_compliance_score),
        }
