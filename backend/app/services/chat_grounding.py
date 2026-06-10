"""Shared grounding assembly + numeric guard for the chatbot assistant.

This module is the single place that turns cached/stored data into accurate,
structured grounding for both the rule-based and the optional LLM chatbot paths.
It performs no new network calls: it reads ``market_cache`` (prices written by the
market refresh job) and the latest-context bucket (populated through the existing
TTL-bounded ``fetch_latest_asset_context``). It never generates AI reports
(AGENTS.md section 14); report summaries are produced from stored ``AIReport``
rows by the caller.

The guard helpers verify that price/percent numbers in a composed answer come
from the assembled grounding, so the chatbot does not surface fabricated figures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..core.cache import market_cache


def _prices() -> dict[str, Any]:
    prices = market_cache.get("prices")
    return prices if isinstance(prices, dict) else {}


def _prices_as_of() -> str | None:
    last_updated = market_cache.get("last_updated")
    if isinstance(last_updated, dict):
        value = last_updated.get("prices")
        if value:
            return str(value)
    return None


def _infer_currency(ticker: str, group: str | None) -> str | None:
    upper = (ticker or "").upper()
    if upper.endswith(".KS") or upper.endswith(".KQ") or upper == "KRW=X":
        return "KRW"
    if upper.startswith("KTB") or group == "bonds":
        # Treasury yields are expressed in percent, not a currency.
        return "%"
    if upper.startswith("DGS"):
        return "%"
    if upper.endswith("-USD") or group in {"us_top10", "commodities", "cryptos"}:
        return "USD"
    if upper in {"^GSPC", "^IXIC"}:
        return "USD"
    return None


def asset_snapshot(ticker: str | None) -> dict[str, Any] | None:
    """Return a structured snapshot for ``ticker`` from the price cache.

    Absorbs the historical key drift (``price``/``close``/``currentPrice`` and
    ``changePercent``/``change_pct``) in one place so callers get consistent
    fields: ``ticker``, ``name``, ``price``, ``change_pct``, ``currency``,
    ``as_of``. Returns ``None`` when the ticker is not present in the cache.
    """

    if not ticker:
        return None
    for group_name, group in _prices().items():
        if not isinstance(group, dict):
            continue
        for label, payload in group.items():
            if not isinstance(payload, dict):
                continue
            if str(payload.get("symbol")) != ticker:
                continue
            price = payload.get("price", payload.get("close", payload.get("currentPrice")))
            change = payload.get("changePercent", payload.get("change_pct"))
            change_value: float | None
            try:
                change_value = float(change) if change is not None else None
            except (TypeError, ValueError):
                change_value = None
            return {
                "ticker": ticker,
                "name": str(label),
                "price": price,
                "change_pct": change_value,
                "currency": _infer_currency(ticker, str(group_name)),
                "as_of": _prices_as_of(),
            }
    return None


def asset_snippet(ticker: str | None) -> str | None:
    """Human-readable one-line snippet for a single asset, grounded in cache.

    Falls back to a macro overview line set when the ticker is unknown, matching
    the previous ``chat_service._cached_market_snippet`` behavior but with a
    currency and as-of stamp for accuracy.
    """

    snapshot = asset_snapshot(ticker)
    if snapshot is not None:
        parts = [snapshot["name"]]
        if snapshot.get("price") is not None:
            currency = snapshot.get("currency")
            if currency == "%":
                parts.append(f"금리 {snapshot['price']}%")
            elif currency:
                parts.append(f"가격 {snapshot['price']} {currency}")
            else:
                parts.append(f"가격 {snapshot['price']}")
        if snapshot.get("change_pct") is not None:
            parts.append(f"{snapshot['change_pct']:+.2f}%")
        if snapshot.get("as_of"):
            parts.append(f"기준 {snapshot['as_of']}")
        return " ".join(parts)

    lines, _ = macro_overview_lines()
    return ", ".join(lines) if lines else None


def macro_overview_lines(limit: int = 4) -> tuple[list[str], str | None]:
    """Return up to ``limit`` macro change lines plus the price as-of stamp.

    Shared by the LLM grounding and the rule-based market-summary response so
    both paths report the same figures.
    """

    macro = _prices().get("macro") or {}
    lines: list[str] = []
    for label, payload in list(macro.items())[:limit]:
        if not isinstance(payload, dict):
            continue
        change = payload.get("changePercent", payload.get("change_pct", 0))
        try:
            lines.append(f"{label} {float(change or 0):+.2f}%")
        except (TypeError, ValueError):
            continue
    return lines, _prices_as_of()


# --- Numeric guard ---------------------------------------------------------

# Match price/percent style numbers only. Bare small integers (e.g. "10년물",
# "TOP10", "3문장") are intentionally NOT matched so they are never flagged.
_NUMBER_PATTERN = re.compile(
    r"[-+]?\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?"  # thousands-separated, optional %
    r"|[-+]?\$?\d+\.\d+%?"                       # decimal, optional %
    r"|[-+]?\d+(?:\.\d+)?%"                      # integer or decimal with %
)


def _normalize_number(token: str) -> str:
    cleaned = token.strip().lstrip("+")
    cleaned = cleaned.replace("$", "").replace(",", "").replace("%", "")
    # Drop a leading minus and trailing zeros so "+1.50%" and "1.5" match.
    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("-")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return ("-" + cleaned) if (negative and cleaned) else cleaned


def extract_numbers(text: Any) -> set[str]:
    if not isinstance(text, str) or not text:
        return set()
    found = set()
    for match in _NUMBER_PATTERN.findall(text):
        normalized = _normalize_number(match)
        if normalized:
            found.add(normalized)
            # Percent and absolute value share a magnitude; allow both polarities.
            found.add(normalized.lstrip("-"))
    return found


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_walk_strings(item))
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_walk_strings(item))
        return out
    if isinstance(value, (int, float)):
        return [str(value)]
    return []


def collect_grounded_numbers(grounding: dict[str, Any]) -> set[str]:
    """Numbers that appear anywhere in the assembled grounding payload."""

    allowed: set[str] = set()
    for text in _walk_strings(grounding or {}):
        allowed |= extract_numbers(text)
    return allowed


@dataclass
class GuardResult:
    grounded: bool
    ungrounded: list[str] = field(default_factory=list)


def guard_answer(answer: str, grounding: dict[str, Any]) -> GuardResult:
    """Check that price/percent numbers in ``answer`` exist in ``grounding``.

    Returns ``grounded=True`` when every price/percent-style number in the
    answer is backed by the grounding payload. Bare integers are ignored, so
    phrasing like "10년물" or "3문장" never trips the guard.
    """

    answer_numbers = extract_numbers(answer)
    if not answer_numbers:
        return GuardResult(grounded=True)
    allowed = collect_grounded_numbers(grounding)
    ungrounded = sorted(n for n in answer_numbers if n.lstrip("-") not in allowed)
    return GuardResult(grounded=not ungrounded, ungrounded=ungrounded)
