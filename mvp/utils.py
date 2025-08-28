import csv
import logging
import math
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from threading import Thread

import boto3
import pytz
from botocore.client import Config
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


def get_class_constants(class_obj):
    return {
        name: getattr(class_obj, name)
        for name in dir(class_obj)
        if not name.startswith("__") and not callable(getattr(class_obj, name))
    }


def get_days(since, until, date_format=None):
    days = []

    current_day = since
    while current_day < until:
        days.append(current_day.strftime(date_format) if date_format else current_day)
        current_day += timedelta(days=1)

    return days


def get_months(since, until, date_format=None):
    months = []

    current_month = since
    while current_month < until:
        months.append(current_month.strftime(date_format) if date_format else current_month)
        current_month += relativedelta(months=1)

    return months


def get_first_day_week(date):
    weekday = date.weekday()
    substract_days = weekday + 1 if weekday != 6 else 0
    return date - timedelta(days=substract_days)


def get_weeks(since, until, date_format=None):
    weeks = []

    current_week = get_first_day_week(since)
    while current_week < until:
        weeks.append(current_week.strftime(date_format) if date_format else current_week)
        current_week += relativedelta(weeks=1)

    return weeks


def get_since_until_last_record_months(last_record, num_months):
    """Get the start and end dates for a given number of months up to today based on the last record's date."""
    today = get_tz_date(datetime.utcnow().date())

    if last_record:
        since = get_tz_date(last_record.date_time + timedelta(days=1))
    else:
        since = get_months_ago(today, num_months)

    return (since, today)


def get_months_ago(date, num_months):
    months_ago = date - relativedelta(months=num_months)
    return months_ago.replace(day=1)


def get_tz_date(date):
    return timezone.make_aware(datetime.combine(date, datetime.min.time()))


def retry_on_status_code(max_retries, delay, status_codes, exp_base=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if response.status_code not in status_codes:
                        return response
                    # Create exception for potential raising
                    last_exception = HTTPError(response=response)
                except HTTPError as error:
                    last_exception = error
                    if error.response.status_code not in status_codes:
                        raise

                # Don't sleep after the last attempt
                if attempt < max_retries:
                    seconds = delay * (exp_base**attempt)
                    code = last_exception.response.status_code
                    logger.warning(f"Request failed with status {code}. Retrying in {seconds}s...")
                    time.sleep(seconds)

            # If we exit the loop, we have an error to raise
            raise last_exception

        return wrapper

    return decorator


def retry_on_exceptions(max_retries=3, delay=10, exp_base=2, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as error:
                    last_exception = error

                    # Don't sleep after the last attempt
                    if attempt < max_retries:
                        seconds = delay * (exp_base**attempt)
                        logger.warning(f"Operation failed. Retrying in {seconds}s...")
                        time.sleep(seconds)

            # If we exit the loop, log and raise the last exception
            logger.exception(
                f"Max retries ({max_retries}) exceeded. Function '{func.__name__}' failed",
                extra={"retries": max_retries, "delay": delay, "exp_base": exp_base},
            )
            raise last_exception

        return wrapper

    return decorator


def start_new_thread(function):
    def decorator(*args, **kwargs):
        if settings.TESTING:
            function(*args, **kwargs)
        else:
            t = Thread(target=function, args=args, kwargs=kwargs)
            # daemon = True will cause the thread to terminate if the main thread terminates even if it's still running
            t.daemon = False
            t.start()

    return decorator


def traceback_on_debug():
    if settings.DEBUG and not settings.TESTING:
        traceback.print_exc()


def round_half_up(num, d):
    """Source: https://github.com/Semalab/tools/blob/19ce10668b265909315d3c1a5b922c6ea6f3afad/scqp-cli/sc/Report/generate_hc/functions/generic_functions.py#L37."""
    if math.isnan(float(num)):
        return num
    if type(num) is int:
        return float(num)
    multiplier = 10 ** (d)
    num = Decimal(str(num))
    if num >= 0:
        num = Decimal(str(num)) * multiplier
        new_num = Decimal(num) + Decimal("0.5")
        return int(new_num) / multiplier
    new_num = round_half_up(str(Decimal(num) * -1), d) * -1
    if new_num != int(num * multiplier) / multiplier:
        new_num = Decimal(str(new_num)) + Decimal(str(2 / multiplier))
    return float(new_num)


def set_csv_field_size_limit():
    # Source: https://stackoverflow.com/questions/15063936/csv-error-field-larger-than-field-limit-131072
    max_size = sys.maxsize

    while True:
        try:
            csv.field_size_limit(max_size)
            break
        except OverflowError:
            max_size = int(max_size / 10)
            if not max_size:
                logger.exception("Failed to set csv field size limit")
                break


def process_csv_file(file_path, processor, encoding="utf-8", delimiter=None):
    set_csv_field_size_limit()

    num_rows = 0
    with open(file_path, encoding=encoding, errors="ignore") as csvfile:
        if delimiter:
            reader = csv.DictReader(csvfile, delimiter=delimiter)
        else:
            dialect = csv.Sniffer().sniff(csvfile.read(2048), delimiters="\t;,")
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)

        for row in reader:
            processor(row)
            num_rows += 1

    return num_rows


def get_whole_decimal(value):
    whole = int(value)
    decimal = 0
    if value and "." in str(value):
        decimal = str(value).split(".")[1]

    return whole, decimal


def run_command_subprocess(command, cwd=None, stdin: bytes | None = None):
    output = subprocess.run(command, cwd=cwd, capture_output=True, input=stdin)

    if output.returncode != 0:
        return False, output.stderr.decode() if output.stderr else "Unknown error"

    return True, output.stdout.decode()


def clamp(value, min_value=0, max_value=100):
    return max(min_value, min(value, max_value))


def normalize_start_date(start_date: datetime):
    return start_date.replace(hour=0, minute=0, second=0, microsecond=0)


def normalize_end_date(end_date: datetime):
    return end_date.replace(hour=23, minute=59, second=59, microsecond=999999)


@retry_on_exceptions(max_retries=5, delay=1)
def shred_path(path):
    """Recursively delete a directory and its contents using `rm`."""
    subprocess.run(["rm", "-rf", path], check=True)


def get_file_url(file):
    if not file:
        return None

    if settings.DEBUG and not settings.AWS_S3_FORCE_UPLOAD_TO_BUCKET:
        return f"{settings.SITE_DOMAIN}{file.url}"

    return get_pre_signed_url(file)


def get_pre_signed_url(file):
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(signature_version=settings.AWS_S3_SIGNATURE_VERSION),
    )
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": file.name},
        ExpiresIn=settings.AWS_S3_PRE_SIGNED_URL_EXPIRATION,
    )


def remove_empty_lines_from_text(content: str) -> str:
    content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)
    return content.strip()


def get_daily_message_template_context(organization, data, no_commits_message=False, no_data_after_filter=False):
    last_updated = datetime.fromtimestamp(data["last_updated"], tz=pytz.UTC) if data["last_updated"] else None
    return {
        "site_domain": settings.SITE_DOMAIN,
        "organization": organization,
        "last_updated": last_updated,
        "no_commits_message": no_commits_message,
        "no_data_after_filter": no_data_after_filter,
        "data": data,
        "message_date": last_updated.date() if last_updated else None,
    }
