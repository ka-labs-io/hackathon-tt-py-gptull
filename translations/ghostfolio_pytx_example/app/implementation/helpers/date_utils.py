from __future__ import annotations

from datetime import datetime, timedelta

__all__ = [
    "add_milliseconds",
    "difference_in_days",
    "each_year_of_interval",
    "format_date",
    "is_before",
    "is_this_year",
]


def add_milliseconds(dt: datetime, ms: int | float) -> datetime:
    return dt + timedelta(milliseconds=int(ms))


def difference_in_days(later: datetime | str, earlier: datetime | str) -> int:
    left = _ensure_datetime(later)
    right = _ensure_datetime(earlier)
    return (left - right).days


def each_year_of_interval(interval: dict) -> list[datetime]:
    start = _ensure_datetime(interval.get("start", datetime.now()))
    end = _ensure_datetime(interval.get("end", datetime.now()))
    years: list[datetime] = []
    current = datetime(start.year, 1, 1)
    while current <= end:
        years.append(current)
        current = datetime(current.year + 1, 1, 1)
    return years


def format_date(dt: datetime | str, fmt: str = "yyyy-MM-dd") -> str:
    d = _ensure_datetime(dt)
    py_fmt = fmt.replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d")
    return d.strftime(py_fmt)


def is_before(left: datetime | str, right: datetime | str) -> bool:
    return _ensure_datetime(left) < _ensure_datetime(right)


def is_this_year(dt: datetime | str) -> bool:
    return _ensure_datetime(dt).year == datetime.now().year


def _ensure_datetime(val: datetime | str | None) -> datetime:
    if val is None:
        return datetime.now()
    if isinstance(val, str):
        return datetime.fromisoformat(val)
    return val
