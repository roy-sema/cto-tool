from compass.codebasereports.widgets import ChartWidget


class GroupSeriesChartWidget(ChartWidget):
    CHART_MAX_SERIES = 10
    CHART_SERIES_GROUP = "All"

    def parse_stacked_charts_data(self, charts_data, since, until, aggregate=False):
        charts = self.group_charts_series(charts_data)
        return super().parse_stacked_charts_data(charts, since, until, aggregate)

    def group_charts_series(self, charts_data):
        """
        If there are more than max series, then display just
        the total for clarity and performance.
        """
        charts = {}
        for field_name, series_data in charts_data.items():
            if len(series_data.keys()) > self.CHART_MAX_SERIES:
                charts[field_name] = {self.CHART_SERIES_GROUP: self.aggregate_all_series(series_data)}
            else:
                charts[field_name] = series_data

        return charts

    def aggregate_all_series(self, series_data):
        total = {}
        for project_data in series_data.values():
            for day, value in project_data.items():
                if day not in total:
                    total[day] = value
                else:
                    total[day] += value

        return total
