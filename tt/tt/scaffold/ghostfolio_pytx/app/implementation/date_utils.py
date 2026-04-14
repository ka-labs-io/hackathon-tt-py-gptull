from datetime import datetime, timedelta
from typing import Final

__all__: list[str] = [
    "DATE_FORMAT",
    "DATE_FORMAT_MONTHLY",
    "DATE_FORMAT_YEARLY",
    "format_date",
    "is_before",
    "difference_in_days",
    "add_milliseconds",
    "each_year_of_interval",
    "is_this_year",
]

DATE_FORMAT: Final[str] = "yyyy-MM-dd"
DATE_FORMAT_MONTHLY: Final[str] = "MMMM yyyy"
DATE_FORMAT_YEARLY: Final[str] = "yyyy"

_DATEFNS_TO_STRFTIME: Final[dict[str, str]] = {
    "yyyy-MM-dd": "%Y-%m-%d",
    "yyyy": "%Y",
    "MMMM yyyy": "%B %Y",
}


def format_date(date: datetime, fmt: str) -> str:
    return date.strftime(_DATEFNS_TO_STRFTIME.get(fmt, fmt))


def is_before(date_a: datetime, date_b: datetime) -> bool:
    return date_a < date_b


def difference_in_days(date_a: datetime, date_b: datetime) -> int:
    return (date_a - date_b).days


def add_milliseconds(date: datetime, milliseconds: int) -> datetime:
    return date + timedelta(milliseconds=milliseconds)


def each_year_of_interval(start: datetime, end: datetime) -> list[datetime]:
    return [
        datetime(year, 1, 1)
        for year in range(start.year, end.year + 1)
    ]


def is_this_year(date: datetime) -> bool:
    return date.year == datetime.now().year
