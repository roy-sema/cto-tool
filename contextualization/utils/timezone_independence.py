from datetime import datetime, timedelta


def adjust_start_and_end_date_for_timezone_independence(start_date: str, end_date: str):
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    adjusted_start_dt = start_dt - timedelta(days=2)
    adjusted_end_dt = end_dt + timedelta(days=2)

    new_start_date = adjusted_start_dt.strftime("%Y-%m-%d")
    new_end_date = adjusted_end_dt.strftime("%Y-%m-%d")

    return new_start_date, new_end_date
