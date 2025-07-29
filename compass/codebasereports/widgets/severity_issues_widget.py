from abc import abstractmethod

from compass.codebasereports.widgets import ChartWidget


class SeverityIssuesWidget(ChartWidget):
    SERIES_ORDER = {"low": 0, "medium": 1, "medium_high": 2, "high": 3, "critical": 4}

    @property
    @abstractmethod
    def integration(self):
        pass

    @property
    @abstractmethod
    def severity(self):
        pass

    def parse_stacked_charts_data(self, charts_data, since, until, aggregate=False):
        return super().parse_stacked_charts_data(self.group_issues(charts_data), since, until, aggregate)

    def group_issues(self, charts):
        """
        Group issues for all projects into one chart for each type
        """
        for issue_type in self.integration.SEVERITY_ISSUE_TYPES:
            has_records = False
            levels = self.get_severity_levels(issue_type)
            sorted_levels = sorted(levels, key=lambda level: self.SERIES_ORDER[level])
            series = {level: {} for level in sorted_levels if level != self.severity.CRITICAL}

            for level in levels:
                field_name = self.integration.get_issue_count_field_name(issue_type, level)

                if field_name in charts:
                    has_records = True
                    series_name = self.normalize_severity_level(level)

                    for project_name, project_data in charts[field_name].items():
                        for day, value in project_data.items():
                            if day not in series[series_name]:
                                series[series_name][day] = 0

                            series[series_name][day] += value

                    del charts[field_name]

            if has_records:
                charts[issue_type] = series

        return charts

    def normalize_severity_level(self, level):
        """
        Combine "high" + "critical" as "high"
        """
        return self.severity.HIGH if level == self.severity.CRITICAL else level

    def get_severity_levels(self, issue_type):
        return (
            self.integration.get_issue_type_levels(issue_type)
            if getattr(self.integration, "get_issue_type_levels", None)
            else self.integration.SEVERITY_LEVELS
        )
