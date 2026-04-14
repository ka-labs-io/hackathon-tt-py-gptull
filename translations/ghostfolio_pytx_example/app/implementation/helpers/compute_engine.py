from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.implementation.helpers.date_utils import format_date


__all__ = [
    "prepare_snapshot_data",
    "compute_snapshot",
    "make_performance_response",
    "make_investments_response",
    "make_holdings_response",
    "make_details_response",
    "make_dividends_response",
    "make_report_response",
]


def compute_snapshot(calculator: object) -> dict:
    activities = getattr(calculator, "activities", []) or []
    rate_svc = getattr(calculator, "current_rate_service", None)

    normalized = _normalize_activities(activities)

    original_activities = calculator.activities
    calculator.activities = normalized

    data = prepare_snapshot_data(normalized, rate_svc)

    items = data["transaction_items"]
    positions = []
    for item in items:
        metrics = calculator.get_symbol_metrics(
            data["chart_date_map"],
            item["dataSource"],
            data["end"],
            data["exchange_rates"],
            data["market_symbol_map"],
            data["start"],
            item["symbol"],
        )
        pos = {**item, **metrics}
        pos["includeInTotalAssetValue"] = True
        pos.setdefault("investment", pos.get("totalInvestment", Decimal(0)))
        pos.setdefault("investmentWithCurrencyEffect", pos.get("totalInvestmentWithCurrencyEffect", Decimal(0)))
        pos.setdefault("feeInBaseCurrency", pos.get("feesWithCurrencyEffect", Decimal(0)))
        qty = float(item.get("quantity", 0))
        price = float(item.get("averagePrice", 0))
        pos["valueInBaseCurrency"] = qty * price
        positions.append(pos)

    calculator.activities = original_activities

    return calculator.calculate_overall_performance(positions)


def _normalize_activities(activities: list[dict]) -> list[dict]:
    result = []
    for a in activities:
        normalized = dict(a)
        if "SymbolProfile" not in normalized:
            normalized["SymbolProfile"] = {
                "symbol": a.get("symbol", ""),
                "dataSource": a.get("dataSource", "YAHOO"),
                "assetSubClass": None,
            }
        if "date" in normalized and isinstance(normalized["date"], datetime):
            normalized["date"] = format_date(normalized["date"])
        if "fee" in normalized and not isinstance(normalized["fee"], Decimal):
            normalized["fee"] = Decimal(str(normalized["fee"]))
        if "feeInBaseCurrency" not in normalized:
            normalized["feeInBaseCurrency"] = normalized.get("fee", Decimal(0))
        if "quantity" in normalized and not isinstance(normalized["quantity"], Decimal):
            normalized["quantity"] = Decimal(str(normalized["quantity"]))
        if "unitPrice" in normalized and not isinstance(normalized["unitPrice"], Decimal):
            normalized["unitPrice"] = Decimal(str(normalized["unitPrice"]))
        result.append(normalized)
    return result


def make_performance_response(calculator: object, snapshot: dict) -> dict:
    sorted_acts = calculator.sorted_activities()
    first_date = min((a["date"] for a in sorted_acts), default=None)
    perf = {}
    for k, v in snapshot.items():
        if not isinstance(v, (list, dict)):
            perf[k] = float(v) if hasattr(v, "__float__") else v
    return {
        "chart": snapshot.get("historicalData", []),
        "firstOrderDate": first_date,
        "performance": perf,
    }


def make_investments_response(
    calculator: object,
    snapshot: dict,
    group_by: str | None = None,
) -> dict:
    return {"investments": []}


def make_holdings_response(calculator: object, snapshot: dict) -> dict:
    return {"holdings": {}}


def make_details_response(
    calculator: object,
    snapshot: dict,
    base_currency: str = "USD",
) -> dict:
    return {
        "accounts": {},
        "holdings": {},
        "platforms": {},
        "summary": {},
        "hasError": False,
    }


def make_dividends_response(
    calculator: object,
    snapshot: dict,
    group_by: str | None = None,
) -> dict:
    return {"dividends": []}


def make_report_response(calculator: object) -> dict:
    return {
        "xRay": {
            "categories": [],
            "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0},
        }
    }


def prepare_snapshot_data(
    activities: list[dict],
    rate_svc: object,
) -> dict:
    if not activities:
        return _empty_snapshot_data()

    symbols = _unique_symbols(activities)
    date_range = _date_range(activities)
    start_str, end_str = date_range["start"], date_range["end"]

    market_symbol_map = _build_market_symbol_map(symbols, rate_svc, start_str, end_str)
    exchange_rates = _build_exchange_rates(start_str, end_str, rate_svc, activities)
    chart_date_map = _build_chart_date_map(start_str, end_str, rate_svc)
    transaction_items = _build_transaction_items(activities, symbols)

    return {
        "market_symbol_map": market_symbol_map,
        "exchange_rates": exchange_rates,
        "chart_date_map": chart_date_map,
        "start": datetime.fromisoformat(start_str),
        "end": datetime.fromisoformat(end_str),
        "start_str": start_str,
        "end_str": end_str,
        "transaction_items": transaction_items,
        "symbols": symbols,
    }


def _empty_snapshot_data() -> dict:
    now = datetime.now()
    return {
        "market_symbol_map": {},
        "exchange_rates": {},
        "chart_date_map": {},
        "start": now,
        "end": now,
        "start_str": format_date(now),
        "end_str": format_date(now),
        "transaction_items": [],
        "symbols": set(),
    }


def _unique_symbols(activities: list[dict]) -> set[str]:
    return {a["symbol"] for a in activities if a.get("symbol")}


def _date_range(activities: list[dict]) -> dict:
    dates = [a["date"] for a in activities if a.get("date")]
    if not dates:
        today = format_date(datetime.now())
        return {"start": today, "end": today}
    start = format_date(min(dates))
    end = format_date(datetime.now())
    return {"start": start, "end": end}


def _build_market_symbol_map(
    symbols: set[str],
    rate_svc: object,
    start: str,
    end: str,
) -> dict[str, dict[str, Decimal]]:
    result: dict[str, dict[str, Decimal]] = {}
    all_dates = getattr(rate_svc, "all_dates_in_range", lambda s, e: set())(start, end)

    for date_str in sorted(all_dates):
        for sym in symbols:
            price = getattr(rate_svc, "get_price", lambda s, d: None)(sym, date_str)
            if price is not None:
                result.setdefault(date_str, {})[sym] = Decimal(str(price))

    today_str = format_date(datetime.now())
    for sym in symbols:
        latest = getattr(rate_svc, "get_latest_price", lambda s: 0.0)(sym)
        if latest and latest > 0:
            result.setdefault(today_str, {})[sym] = Decimal(str(latest))

    return result


def _build_exchange_rates(
    start: str,
    end: str,
    rate_svc: object,
    activities: list[dict] | None = None,
) -> dict[str, float]:
    rates: dict[str, float] = {}
    all_dates = getattr(rate_svc, "all_dates_in_range", lambda s, e: set())(start, end)
    for d in all_dates:
        rates[d] = 1.0
    today_str = format_date(datetime.now())
    rates[today_str] = 1.0
    rates[start] = 1.0
    rates[end] = 1.0
    if activities:
        for a in activities:
            d = a.get("date", "")
            if d:
                rates[d] = 1.0
    return rates


def _build_chart_date_map(start: str, end: str, rate_svc: object) -> dict[str, bool]:
    chart_map: dict[str, bool] = {}
    all_dates = getattr(rate_svc, "all_dates_in_range", lambda s, e: set())(start, end)
    for d in sorted(all_dates):
        chart_map[d] = True
    today_str = format_date(datetime.now())
    chart_map[today_str] = True
    chart_map[start] = True
    chart_map[end] = True
    return chart_map


def _build_transaction_items(
    activities: list[dict],
    symbols: set[str],
) -> list[dict]:
    items: list[dict] = []
    for sym in sorted(symbols):
        sym_activities = [a for a in activities if a.get("symbol") == sym]
        if not sym_activities:
            continue

        total_qty = Decimal(0)
        total_fee = Decimal(0)
        total_fee_base = Decimal(0)
        avg_price = Decimal(0)
        currency = sym_activities[0].get("currency", "USD")
        data_source = sym_activities[0].get("dataSource", "YAHOO")
        first_date = sym_activities[0].get("date")
        acts_count = 0

        for a in sym_activities:
            qty = Decimal(str(a.get("quantity", 0)))
            price = Decimal(str(a.get("unitPrice", 0)))
            fee = Decimal(str(a.get("fee", 0)))
            act_type = a.get("type", "")

            if act_type == "BUY":
                total_qty += qty
                avg_price = (
                    price
                    if total_qty == qty
                    else (avg_price * (total_qty - qty) + price * qty) / total_qty
                )
                acts_count += 1
            elif act_type == "SELL":
                total_qty -= qty
                acts_count += 1

            total_fee += fee
            total_fee_base += fee

        items.append({
            "activitiesCount": acts_count,
            "averagePrice": avg_price,
            "currency": currency,
            "dataSource": data_source,
            "dateOfFirstActivity": first_date,
            "fee": total_fee,
            "feeInBaseCurrency": total_fee_base,
            "includeInHoldings": True,
            "investment": total_qty * avg_price,
            "quantity": total_qty,
            "symbol": sym,
            "tags": [],
            "assetSubClass": None,
            "skipErrors": False,
        })

    return items
