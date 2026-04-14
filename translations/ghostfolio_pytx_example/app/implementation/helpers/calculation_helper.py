from __future__ import annotations

from datetime import datetime, timedelta

__all__ = ["get_interval_from_date_range"]


def get_interval_from_date_range(
    date_range: str,
    start_date_override: datetime | None = None,
) -> dict:
    today = datetime.now()

    range_map = {
        "1d": lambda: (today - timedelta(days=1), today),
        "wtd": lambda: (today - timedelta(days=today.weekday()), today),
        "mtd": lambda: (today.replace(day=1), today),
        "ytd": lambda: (today.replace(month=1, day=1), today),
        "1y": lambda: (today.replace(year=today.year - 1), today),
        "5y": lambda: (today.replace(year=today.year - 5), today),
        "max": lambda: (start_date_override or datetime(2000, 1, 1), today),
    }

    if date_range.isdigit() and len(date_range) == 4:
        year = int(date_range)
        return {
            "startDate": datetime(year, 1, 1),
            "endDate": datetime(year, 12, 31),
        }

    resolver = range_map.get(date_range, range_map["max"])
    start, end = resolver()
    return {"startDate": start, "endDate": end}
