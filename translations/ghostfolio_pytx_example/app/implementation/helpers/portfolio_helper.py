from __future__ import annotations

__all__ = ["get_factor"]


_FACTOR_MAP: dict[str, int] = {
    "BUY": 1,
    "SELL": -1,
    "DIVIDEND": 0,
    "FEE": 0,
    "INTEREST": 0,
    "LIABILITY": 0,
}


def get_factor(activity_type: str) -> int:
    return _FACTOR_MAP.get(activity_type, 0)
