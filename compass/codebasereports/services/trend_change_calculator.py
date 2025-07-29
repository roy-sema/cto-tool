from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TrendChangeConfig:
    commit_delta: float = 0.05
    moving_window: int = 1
    perc_dec_thres: float = 0.2
    perc_inc_thres: float = 0.1
    risk_threshold: float = 0.4
    use_average: bool = True


class TrendChangeCalculator:
    EVALUATION_HIGH_RISK = 1
    EVALUATION_MEDIUM_RISK = 2
    EVALUATION_LOW_RISK = 3
    EVALUATION_STRENGTH = 4

    LAST_NUM_MONTHS = 6

    def average_developer_activity(self, records, conf: TrendChangeConfig):
        df = self.records_to_df(records)
        df = df.groupby(["year", "month"]).agg({"commits": "sum", "member__external_id": "nunique"})
        df["commits_per_member"] = df["commits"] / df["member__external_id"]
        return self.calculate_trend(df, "commits_per_member", conf)

    def commit_analysis(self, records, conf: TrendChangeConfig):
        df = self.records_to_df(records)
        df = df.groupby(["year", "month"])[["commits"]].sum()
        return self.calculate_trend(df, "commits", conf)

    def developers_and_development_activity(self, records, conf: TrendChangeConfig):
        df = self.records_to_df(records)
        df = df.groupby(["year", "month"])[["member__external_id"]].nunique()
        return self.calculate_trend(df, "member__external_id", conf)

    def records_to_df(self, records):
        df = pd.DataFrame.from_records(records)
        df["date_time"] = pd.to_datetime(df["date_time"])
        df["month"] = df["date_time"].dt.month
        df["year"] = df["date_time"].dt.year
        return df

    def calculate_trend(self, df, column_name, conf: TrendChangeConfig):
        df = df.rolling(conf.moving_window, min_periods=1).mean()
        y = df[column_name].values

        df_months = df.iloc[-self.LAST_NUM_MONTHS :]
        y_last_months = df_months[column_name].values

        global_maxima = y_last_months.max()
        global_maxima_date = df_months[column_name].idxmax()

        global_minima = y_last_months.min()
        global_minima_date = df_months[column_name].idxmin()

        perc_dec_last_months = (y_last_months[-1] - global_maxima) / global_maxima
        perc_inc_last_months = (y_last_months[-1] - global_minima) / global_minima

        if perc_dec_last_months <= -conf.perc_dec_thres:
            return self.EVALUATION_HIGH_RISK

        if perc_inc_last_months > conf.perc_inc_thres:
            return self.EVALUATION_STRENGTH

        (
            time_periods_inc,
            perc_diff_inc,
            time_periods_dec,
            perc_diff_dec,
        ) = self.evaluate_time_periods(y_last_months, df_months, conf, y.mean())
        time_periods_inc.extend(time_periods_dec)
        perc_diff_inc.extend(perc_diff_dec)

        df_temp = pd.DataFrame(columns=["Start", "End", "Percentage Difference"])
        df_temp["Start"] = [x[0] for x in time_periods_inc]
        df_temp["End"] = [x[1] for x in time_periods_inc]
        df_temp["Percentage Difference"] = perc_diff_inc

        df_temp = df_temp[df_temp["Percentage Difference"] > conf.commit_delta]
        df_temp.sort_values(by=["Percentage Difference"], inplace=True, ascending=False)
        if df_temp.shape[0] == 0:
            return self.EVALUATION_STRENGTH

        if df_temp.shape[0] >= 2:
            df_temp = df_temp.iloc[:2, :]
            df_temp = df_temp.sort_values(by=["Start"], ascending=True)
            df_temp = df_temp.reset_index(drop=True)

        risk_type = [self.EVALUATION_LOW_RISK, self.EVALUATION_MEDIUM_RISK][
            int(df_temp["Percentage Difference"].max() > conf.risk_threshold)
        ]
        return risk_type

    def evaluate_time_periods(self, y, df, conf: TrendChangeConfig, y_avg=None):
        if y_avg is None:
            y_avg = y.mean()
        prev = y[0]
        # get whether it's increasing or decreasing
        is_increasing = [None]
        increasing = None
        for ele in y[1:]:
            if ele > prev:
                increasing = 1
            elif ele < prev:
                increasing = 0
            prev = ele
            is_increasing.append(increasing)

        # fill in the None values
        for i in range(-1, -len(is_increasing) - 1, -1):
            if is_increasing[i] is None:
                is_increasing[i] = is_increasing[i + 1]

        # initialize minima and maxima arrays
        minima = []
        maxima = []
        # get first minima and maxima
        i = 0
        while i < len(y) - 1:
            if y[i] < y[i + 1]:
                minima.append(i)
                break
            elif y[i] == y[i + 1]:
                i += 1
            elif y[i] > y[i + 1]:
                maxima.append(i)
                break
        # get the rest of the minima and maxima
        for i in range(len(is_increasing) - 1):
            if (is_increasing[i] == 0) and (is_increasing[i + 1] == 1):
                minima.append(i)
            if (is_increasing[i] == 1) and (is_increasing[i + 1] == 0):
                maxima.append(i)
        # get last minima and maxima
        i = len(y) - 1
        while i > 0:
            if y[i] < y[i - 1]:
                minima.append(i)
                break
            elif y[i] == y[i - 1]:
                i -= 1
            elif y[i] > y[i - 1]:
                maxima.append(i)
                break
        # zip minima and maxima along with their percentage difference
        time_periods_inc = []
        perc_diff_inc = []
        time_periods_dec = []
        perc_diff_dec = []
        for mn in minima:
            for mx in maxima:
                if mn < mx:
                    time_periods_inc.append((df.index[mn], df.index[mx]))
                    if conf.use_average:
                        perc_diff_inc.append((y[mx] - y[mn]) / y_avg)
                    else:
                        perc_diff_inc.append((y[mx] - y[mn]) / y[mn])
                    break
        for mx in maxima:
            for mn in minima:
                if mn > mx:
                    time_periods_dec.append((df.index[mx], df.index[mn]))
                    if conf.use_average:
                        perc_diff_dec.append((y[mx] - y[mn]) / y_avg)
                    else:
                        perc_diff_dec.append((y[mx] - y[mn]) / y[mx])
                    break
        return time_periods_inc, perc_diff_inc, time_periods_dec, perc_diff_dec
