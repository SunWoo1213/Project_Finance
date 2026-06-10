from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from ..core.cache import market_cache
from .market_service import (
    BONDS,
    COMMODITIES,
    CRYPTOS,
    FX,
    INDICES,
    KR_BONDS,
    KR_TOP10,
    US_TOP10,
)


@dataclass(frozen=True)
class AssetCandidate:
    ticker: str
    name: str
    category: str
    route_type: str = "detail"
    score: float = 0.72

    @property
    def route(self) -> str:
        prefix = "/market" if self.route_type == "market" else "/detail"
        return f"{prefix}/{quote(self.ticker, safe='')}"


CATEGORY_ROUTES = {
    "macro": {
        "label": "주요 지수·환율",
        "route": "/category/macro",
        "keywords": ["주요지수", "주요 지수", "지수", "환율", "달러", "원달러", "원/달러", "macro"],
    },
    "us_top10": {
        "label": "미국 주식 TOP10",
        "route": "/category/us_top10",
        "keywords": ["미국주식", "미국 주식", "미장", "나스닥 종목", "us top", "미국 top"],
    },
    "kr_top10": {
        "label": "한국 주식 TOP10",
        "route": "/category/kr_top10",
        "keywords": ["한국주식", "한국 주식", "국장", "코스피 종목", "한국 top"],
    },
    "bonds": {
        "label": "채권",
        "route": "/category/bonds",
        "keywords": ["채권", "국채", "금리", "국고채", "treasury", "bond"],
    },
    "commodities": {
        "label": "원자재",
        "route": "/category/commodities",
        "keywords": ["원자재", "금", "은", "commodity", "commodities"],
    },
    "cryptos": {
        "label": "암호화폐",
        "route": "/category/cryptos",
        "keywords": ["암호화폐", "가상화폐", "코인", "crypto", "cryptos"],
    },
}

FEATURE_KEYWORDS = {
    "auth": ["로그인", "계정", "구글", "권한", "인증"],
    "report": ["리포트", "보고서", "분석", "ai", "AI", "요약"],
    "community": ["댓글", "토론", "종토방", "신고", "좋아요", "커뮤니티"],
    "favorite": ["즐겨찾기", "관심", "별", "favorite"],
    "market_summary": ["시장 요약", "오늘 시장", "뉴스", "일정", "캘린더", "시황"],
    "current_page": ["현재 화면", "이 화면", "여기", "현재 페이지"],
}

FINANCIAL_KEYWORDS = [
    "주식",
    "시장",
    "투자",
    "금융",
    "자산",
    "가격",
    "시세",
    "차트",
    "뉴스",
    "리포트",
    "보고서",
    "지수",
    "환율",
    "채권",
    "국채",
    "원자재",
    "코인",
    "암호화폐",
    "비트코인",
    "이더리움",
    "로그인",
    "댓글",
    "토론",
    "즐겨찾기",
    "삼성",
    "테슬라",
    "나스닥",
    "코스피",
    "s&p",
    "nasdaq",
    "kospi",
    "usd",
    "krw",
]

NON_FINANCIAL_HINTS = [
    "저녁",
    "먹을까",
    "요리",
    "날씨",
    "여행",
    "번역",
    "파이썬",
    "코딩",
    "게임",
    "역사",
    "연예",
]


def normalize_query(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def display_name_for_ticker(ticker: str) -> str:
    for candidate in _static_assets():
        if candidate.ticker.upper() == ticker.upper():
            return candidate.name
    return ticker


def is_financial_query(query: str) -> bool:
    normalized = normalize_query(query)
    if not normalized:
        return False
    if any(keyword.lower() in normalized for keyword in FINANCIAL_KEYWORDS):
        return True
    if re.search(r"\b\d{6}(\.ks|\.kq)?\b", normalized):
        return True
    for candidate in _static_assets():
        ticker = candidate.ticker.lower()
        if ticker in normalized or ticker.replace(".ks", "") in normalized:
            return True
    # Keep the financial gate aligned with entity resolution: any known asset
    # alias/name or category keyword counts as financial, so newly added
    # aliases (e.g. 네이버, 엘지엔솔, 브로드컴) are not rejected as off-topic.
    compact = normalized.replace(" ", "")
    for _candidate, aliases in _asset_aliases():
        for alias in aliases:
            alias_norm = normalize_query(alias)
            alias_compact = alias_norm.replace(" ", "")
            if alias_norm and (alias_norm in normalized or alias_compact in compact):
                return True
    if find_category(query) is not None:
        return True
    return False


def detect_feature(query: str) -> str | None:
    normalized = normalize_query(query)
    for feature, keywords in FEATURE_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            return feature
    return None


def find_category(query: str) -> dict | None:
    normalized = normalize_query(query).replace(" ", "")
    for category_key, payload in CATEGORY_ROUTES.items():
        if any(keyword.lower().replace(" ", "") in normalized for keyword in payload["keywords"]):
            return {"key": category_key, **payload}
    return None


def category_action(category: dict, confidence: float = 0.76) -> dict:
    return {
        "type": "navigate",
        "label": f"{category['label']} 목록 보기",
        "url": category["route"],
        "reason": f"{category['label']} 카테고리 요청으로 해석했습니다.",
        "confidence": confidence,
        "requires_auth": False,
    }


def action_for_asset(candidate: AssetCandidate, label_suffix: str = "보기", confidence: float | None = None) -> dict:
    label = f"{candidate.name} {'스냅샷' if candidate.route_type == 'market' else '상세'} {label_suffix}"
    return {
        "type": "navigate",
        "label": label,
        "url": candidate.route,
        "reason": f"{candidate.name}을(를) {candidate.ticker}로 해석했습니다.",
        "confidence": confidence if confidence is not None else candidate.score,
        "requires_auth": False,
    }


def login_action(reason: str = "로그인이 필요한 기능입니다.") -> dict:
    return {
        "type": "login",
        "label": "로그인하기",
        "url": "/login",
        "reason": reason,
        "confidence": 0.92,
        "requires_auth": True,
    }


def card_for_asset(candidate: AssetCandidate) -> dict:
    return {
        "type": "asset",
        "ticker": candidate.ticker,
        "name": candidate.name,
        "category": candidate.category,
        "route": candidate.route,
    }


def ambiguous_bond_candidates() -> list[AssetCandidate]:
    return [
        AssetCandidate("DGS10", "미국 10년물 국채", "bonds", score=0.64),
        AssetCandidate("KTB_10Y", "한국 10년물 국고채", "bonds", score=0.61),
    ]


def find_asset_candidates(query: str, limit: int = 5) -> list[AssetCandidate]:
    normalized = normalize_query(query)
    compact = normalized.replace(" ", "")
    candidates: dict[str, AssetCandidate] = {}

    for candidate, aliases in _asset_aliases():
        alias_match = False
        for alias in aliases:
            alias_norm = normalize_query(alias)
            alias_compact = alias_norm.replace(" ", "")
            if alias_norm and (alias_norm in normalized or alias_compact in compact):
                alias_match = True
                break

        ticker_norm = candidate.ticker.lower()
        direct_ticker = ticker_norm in normalized or ticker_norm.replace(".ks", "") in normalized
        if alias_match or direct_ticker:
            score = 0.92 if alias_match else 0.82
            candidates[candidate.ticker] = AssetCandidate(
                candidate.ticker,
                candidate.name,
                candidate.category,
                candidate.route_type,
                score=score,
            )

    for candidate in _cached_assets():
        label_norm = normalize_query(candidate.name)
        ticker_norm = candidate.ticker.lower()
        if label_norm in normalized or ticker_norm in normalized:
            candidates.setdefault(candidate.ticker, candidate)

    ticker_like = _extract_ticker_like(query)
    if ticker_like and ticker_like not in candidates:
        candidates[ticker_like] = AssetCandidate(ticker_like, ticker_like, "unknown", score=0.58)

    return sorted(candidates.values(), key=lambda item: item.score, reverse=True)[:limit]


def _extract_ticker_like(query: str) -> str | None:
    raw = (query or "").strip()
    upper = raw.upper()
    stock_code_match = re.search(r"\b(\d{6})(\.KS|\.KQ)?\b", upper)
    if stock_code_match:
        code, suffix = stock_code_match.groups()
        return f"{code}{suffix or '.KS'}"

    match = re.search(r"\b[A-Z]{1,5}(-USD)?\b", upper)
    if match:
        token = match.group(0)
        if token in {"AI", "USD", "KRW"}:
            return None
        return token
    return None


def _static_assets() -> list[AssetCandidate]:
    return [
        *[AssetCandidate(ticker, name, "macro", "market") for name, ticker in INDICES.items()],
        *[AssetCandidate(ticker, "원/달러 환율", "macro", "market") for _name, ticker in FX.items()],
        *[AssetCandidate(ticker, name, "us_top10") for name, ticker in US_TOP10.items()],
        *[AssetCandidate(ticker, _kr_name(name), "kr_top10") for name, ticker in KR_TOP10.items()],
        *[AssetCandidate(ticker, _bond_name(name), "bonds") for name, ticker in BONDS.items()],
        *[AssetCandidate(ticker, _bond_name(name), "bonds") for name, ticker in KR_BONDS.items()],
        *[AssetCandidate(ticker, _commodity_name(name), "commodities") for name, ticker in COMMODITIES.items()],
        *[AssetCandidate(ticker, _crypto_name(name), "cryptos") for name, ticker in CRYPTOS.items()],
    ]


def _asset_aliases() -> list[tuple[AssetCandidate, list[str]]]:
    aliases = {
        "^GSPC": ["s&p", "s&p500", "sp500", "에스앤피", "에스앤피500"],
        "^IXIC": ["nasdaq", "nasdaq composite", "나스닥", "나스닥종합", "나스닥 종합", "컴포지트", "나스닥100", "nasdaq100"],
        "^KS11": ["kospi", "코스피"],
        "^KQ11": ["kosdaq", "코스닥"],
        "KRW=X": ["환율", "달러", "원달러", "원/달러", "usdk rw", "usdkrw"],
        "TSLA": ["tesla", "테슬라", "테스라"],
        "AAPL": ["apple", "애플"],
        "MSFT": ["microsoft", "마이크로소프트", "ms"],
        "NVDA": ["nvidia", "엔비디아", "엔비"],
        "GOOGL": ["google", "alphabet", "구글", "알파벳"],
        "AMZN": ["amazon", "아마존"],
        "META": ["meta", "메타", "페이스북", "facebook"],
        "BRK-B": ["berkshire", "버크셔", "버크셔해서웨이"],
        "LLY": ["eli lilly", "lilly", "일라이릴리", "릴리"],
        "AVGO": ["broadcom", "브로드컴"],
        "005930.KS": ["삼성전자", "삼성", "005930"],
        "000660.KS": ["sk하이닉스", "에스케이하이닉스", "하이닉스", "000660"],
        "373220.KS": ["lg에너지솔루션", "엘지에너지솔루션", "엘지엔솔", "lg엔솔", "373220"],
        "207940.KS": ["삼성바이오로직스", "삼바", "207940"],
        "005380.KS": ["현대차", "현대자동차", "005380"],
        "000270.KS": ["기아", "기아차", "000270"],
        "068270.KS": ["셀트리온", "068270"],
        "005490.KS": ["posco", "포스코", "포스코홀딩스", "005490"],
        "035420.KS": ["naver", "네이버", "035420"],
        "105560.KS": ["kb금융", "케이비금융", "국민은행", "105560"],
        "BTC-USD": ["bitcoin", "btc", "비트코인", "비트"],
        "ETH-USD": ["ethereum", "eth", "이더리움", "이더"],
        "XAU": ["gold", "금"],
        "XAG": ["silver", "은"],
        "DGS10": ["미국10년물", "미국 10년물", "미국 국채", "us 10y", "dgs10"],
        "DGS3MO": ["미국3개월물", "미국 3개월물", "us 3m", "dgs3mo"],
        "KTB_10Y": ["한국10년물", "한국 10년물", "한국 국채", "국고채", "ktb_10y"],
        "KTB_1Y": ["한국1년물", "한국 1년물", "ktb_1y"],
    }
    by_ticker = {candidate.ticker: candidate for candidate in _static_assets()}
    return [(candidate, [candidate.name, candidate.ticker, *aliases.get(candidate.ticker, [])]) for candidate in by_ticker.values()]


def _cached_assets() -> list[AssetCandidate]:
    candidates: list[AssetCandidate] = []
    for group_name, group in (market_cache.get("prices") or {}).items():
        if not isinstance(group, dict):
            continue
        for label, payload in group.items():
            if not isinstance(payload, dict) or not payload.get("symbol"):
                continue
            route_type = "market" if group_name == "macro" else "detail"
            candidates.append(
                AssetCandidate(
                    ticker=str(payload["symbol"]),
                    name=str(label),
                    category=str(group_name),
                    route_type=route_type,
                    score=0.7,
                )
            )
    return candidates


def _kr_name(name: str) -> str:
    names = {
        "Samsung Electronics": "삼성전자",
        "SK Hynix": "SK하이닉스",
        "LG Energy Solution": "LG에너지솔루션",
        "Samsung Biologics": "삼성바이오로직스",
        "Hyundai Motor": "현대차",
        "Kia": "기아",
        "Celltrion": "셀트리온",
        "POSCO Holdings": "POSCO홀딩스",
        "NAVER": "NAVER",
        "KB Financial Group": "KB금융",
    }
    return names.get(name, name)


def _bond_name(name: str) -> str:
    names = {
        "US 3M Treasury": "미국 3개월물 국채",
        "US 10Y Treasury": "미국 10년물 국채",
        "KR 1Y Treasury": "한국 1년물 국고채",
        "KR 10Y Treasury": "한국 10년물 국고채",
        "KR 30Y Treasury": "한국 30년물 국고채",
    }
    return names.get(name, name)


def _commodity_name(name: str) -> str:
    return {"Gold": "금", "Silver": "은"}.get(name, name)


def _crypto_name(name: str) -> str:
    return {"Bitcoin": "비트코인", "Ethereum": "이더리움"}.get(name, name)
