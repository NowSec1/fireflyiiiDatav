from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List, Tuple

import requests
import yaml
from dateutil import parser
from dateutil.relativedelta import relativedelta
from flask import Flask, render_template, request


@dataclass
class AppConfig:
    api_base_url: str
    api_token: str
    cache_ttl_minutes: int = 10
    months: int | None = None
    period_start: date | None = None
    period_end: date | None = None


class ConfigError(RuntimeError):
    """Raised when the configuration file is missing or invalid."""


def load_config() -> AppConfig:
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise ConfigError(
            "Missing config.yaml. Copy config.example.yaml, rename it to config.yaml, and set api_base_url/api_token."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    try:
        api_base_url = raw["api_base_url"].rstrip("/")
        api_token = raw["api_token"]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ConfigError(f"Configuration is missing required key: {exc.args[0]}") from exc

    months_raw = raw.get("months")
    months: int | None = None
    if months_raw is not None:
        months = int(months_raw)
        if months <= 0:
            raise ConfigError("`months` must be a positive integer")

    period_config_raw = raw.get("period", {}) or {}
    if not isinstance(period_config_raw, dict):
        raise ConfigError("`period` must be a mapping with `start`/`end` keys")
    period_config = period_config_raw
    period_start_value = period_config.get("start")
    period_end_value = period_config.get("end")

    period_start: date | None = None
    period_end: date | None = None

    if period_start_value:
        try:
            period_start = date.fromisoformat(str(period_start_value))
        except ValueError as exc:
            raise ConfigError("`period.start` must be in YYYY-MM-DD format") from exc

    if period_end_value:
        try:
            period_end = date.fromisoformat(str(period_end_value))
        except ValueError as exc:
            raise ConfigError("`period.end` must be in YYYY-MM-DD format") from exc

    today = date.today()
    if period_end is None:
        period_end = today

    reference_date = period_end
    if period_start is None and months is not None:
        period_start = month_start(reference_date) - relativedelta(months=months - 1)
    elif period_start is None:
        period_start = date(reference_date.year, 1, 1)

    if period_end < period_start:
        raise ConfigError("`period.end` must not be earlier than the start date")

    cache_ttl = int(raw.get("cache_ttl_minutes", 10))
    if cache_ttl <= 0:
        raise ConfigError("`cache_ttl_minutes` must be a positive integer")

    return AppConfig(
        api_base_url=api_base_url,
        api_token=api_token,
        cache_ttl_minutes=cache_ttl,
        months=months,
        period_start=period_start,
        period_end=period_end,
    )


class FireflyClient:
    def __init__(self, config: AppConfig) -> None:
        self.base_url = config.api_base_url
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {config.api_token}",
        }

    def fetch_transactions(
        self,
        transaction_type: str,
        start_date: date,
        end_date: date,
        page_size: int = 100,
    ) -> List[Dict[str, object]]:
        """Retrieve transactions of the given type between start_date and end_date."""

        endpoint = f"{self.base_url}/api/v1/transactions"
        page = 1
        transactions: List[Dict[str, object]] = []

        while True:
            params = {
                "type": transaction_type,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "limit": page_size,
                "page": page,
            }
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()

            data = payload.get("data", [])
            for group in data:
                transactions.extend(self._parse_group(group, transaction_type))

            pagination = payload.get("meta", {}).get("pagination", {})
            if page >= pagination.get("total_pages", page):
                break
            page += 1

        return transactions

    @staticmethod
    def _parse_group(group: Dict[str, object], transaction_type: str) -> Iterable[Dict[str, object]]:
        attributes = group.get("attributes", {})
        for transaction in attributes.get("transactions", []):
            amount = Decimal(str(transaction.get("amount", "0")))
            amount = abs(amount)

            booked_at = parser.isoparse(transaction.get("date"))
            category = transaction.get("category_name") or "未分类"
            source = transaction.get("source_name") or "未知账户"
            destination = transaction.get("destination_name") or "未知账户"

            yield {
                "id": transaction.get("transaction_journal_id"),
                "type": transaction_type,
                "booked_at": booked_at,
                "amount": amount,
                "currency": transaction.get("currency_code") or transaction.get("foreign_currency_code") or "",
                "category": category,
                "source": source,
                "destination": destination,
                "description": attributes.get("description", ""),
            }


def month_start(value: date) -> date:
    return value.replace(day=1)


def month_sequence(start: date, end: date) -> List[date]:
    months: List[date] = []
    current = month_start(start)
    end_month = month_start(end)
    while current <= end_month:
        months.append(current)
        current = month_start(current + relativedelta(months=1))
    return months


def aggregate_monthly(transactions: Dict[str, List[Dict[str, object]]], months: List[date]) -> Dict[str, List[float]]:
    buckets: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))

    for tx_type, items in transactions.items():
        for tx in items:
            booked_at: datetime = tx["booked_at"]
            key = month_start(booked_at.date()).strftime("%Y-%m")
            buckets[key][tx_type] += tx["amount"]

    labels: List[str] = []
    series = {"withdrawal": [], "deposit": [], "transfer": [], "net": []}

    for month in months:
        key = month.strftime("%Y-%m")
        labels.append(key)
        withdrawal = buckets[key].get("withdrawal", Decimal("0"))
        deposit = buckets[key].get("deposit", Decimal("0"))
        transfer = buckets[key].get("transfer", Decimal("0"))

        series["withdrawal"].append(float(withdrawal))
        series["deposit"].append(float(deposit))
        series["transfer"].append(float(transfer))
        series["net"].append(float(deposit - withdrawal))

    series["labels"] = labels
    return series


def aggregate_totals(transactions: Dict[str, List[Dict[str, object]]]) -> Dict[str, float]:
    totals = {}
    for tx_type, items in transactions.items():
        totals[tx_type] = float(sum((tx["amount"] for tx in items), Decimal("0")))
    totals["net"] = totals.get("deposit", 0.0) - totals.get("withdrawal", 0.0)
    return totals


def top_breakdown(items: List[Dict[str, object]], key: str, limit: int = 5) -> List[Tuple[str, float]]:
    totals: Dict[str, Decimal] = defaultdict(Decimal)
    for tx in items:
        label = tx.get(key) or "未分类"
        totals[label] += tx["amount"]
    return [
        (name, float(amount))
        for name, amount in sorted(totals.items(), key=lambda pair: pair[1], reverse=True)[:limit]
    ]


def prepare_context(config: AppConfig) -> Dict[str, object]:
    start_date = config.period_start or date(date.today().year, 1, 1)
    end_date = config.period_end or date.today()
    months = month_sequence(start_date, end_date)
    if not months:
        months = [month_start(start_date)]

    client = FireflyClient(config)
    transactions: Dict[str, List[Dict[str, object]]] = {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_map = {
            executor.submit(client.fetch_transactions, tx_type, start_date, end_date): tx_type
            for tx_type in ("withdrawal", "deposit", "transfer")
        }
        for future in as_completed(future_map):
            tx_type = future_map[future]
            transactions[tx_type] = future.result()

    monthly_series = aggregate_monthly(transactions, months)
    totals = aggregate_totals(transactions)
    month_count = max(len(months), 1)

    context = {
        "monthly_labels": monthly_series["labels"],
        "monthly_withdrawals": monthly_series["withdrawal"],
        "monthly_deposits": monthly_series["deposit"],
        "monthly_transfers": monthly_series["transfer"],
        "monthly_net": monthly_series["net"],
        "totals": totals,
        "average_withdrawal": totals.get("withdrawal", 0.0) / month_count,
        "average_deposit": totals.get("deposit", 0.0) / month_count,
        "average_net": totals.get("net", 0.0) / month_count,
        "top_spending_categories": top_breakdown(transactions["withdrawal"], "category"),
        "top_income_categories": top_breakdown(transactions["deposit"], "category"),
        "top_source_accounts": top_breakdown(transactions["withdrawal"], "source"),
        "top_destination_accounts": top_breakdown(transactions["deposit"], "destination"),
        "top_transfer_accounts": top_breakdown(transactions["transfer"], "destination"),
        "last_updated": datetime.utcnow(),
        "date_range": {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
        },
        "months": len(months),
    }
    return context


@dataclass
class CacheEntry:
    value: Dict[str, object]
    expires_at: datetime


class DashboardCache:
    def __init__(self) -> None:
        self._entry: CacheEntry | None = None
        self._lock = Lock()

    def get(self, config: AppConfig, *, force_refresh: bool = False) -> Dict[str, object]:
        ttl = timedelta(minutes=config.cache_ttl_minutes)
        now = datetime.utcnow()

        with self._lock:
            if not force_refresh and self._entry and self._entry.expires_at > now:
                return self._entry.value

        context = prepare_context(config)
        expires_at = now + ttl
        context["cache_ttl_minutes"] = config.cache_ttl_minutes
        context["last_updated_display"] = context["last_updated"].strftime("%Y-%m-%d %H:%M UTC")

        with self._lock:
            self._entry = CacheEntry(value=context, expires_at=expires_at)
        return context


app = Flask(__name__)
dashboard_cache = DashboardCache()


@app.route("/")
def index():
    config = load_config()
    force_refresh = request.args.get("refresh") in {"1", "true", "yes"}
    context = dashboard_cache.get(config, force_refresh=force_refresh)
    return render_template("index.html", **context)


@app.errorhandler(ConfigError)
def handle_config_error(err: ConfigError):
    return render_template("error.html", message=str(err)), 500


@app.errorhandler(requests.HTTPError)
def handle_http_error(err: requests.HTTPError):
    message = "无法从 Firefly III 获取数据，请检查配置和网络后重试。"
    return render_template("error.html", message=f"{message}\n{err}"), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
