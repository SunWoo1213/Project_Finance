"""data.go.kr(공공데이터포털) 도달성 진단용 일회성 스크립트.

배포 로그에서 KR 종목/지수가 빈 `failed:`(=httpx timeout, str(exc)가 빈 문자열)로
떨어지는 원인을 확정하기 위한 도구다. data_go_kr provider 호출을 직렬화(Semaphore(1))
없이 단발로 직접 때려서, 다음을 분류한다:

    - ConnectTimeout / ConnectError → 네트워크/방화벽/DNS로 도달 자체 불가 (egress 차단)
    - ReadTimeout                  → 연결은 되나 서버 응답이 느림
    - HTTPStatusError 4xx          → serviceKey/쿼터 문제 (키만 고치면 됨)
    - 200 OK                       → 단발 호출은 정상 (직렬 큐 누적이 진짜 원인)

serviceKey 값은 절대 출력하지 않는다(설정 여부만 bool로 표시).

실행 (backend 디렉터리에서):
    python -m scripts.probe_data_go
    python -m scripts.probe_data_go --timeout 15 --stock 005930 --index KOSPI
"""

from __future__ import annotations

import argparse
import asyncio
from time import monotonic

import httpx

from app.core.config import settings
from app.services.price_providers import (
    DATA_GO_INDEX_URL,
    DATA_GO_STOCK_URL,
    _data_go_params,
    _recent_basdt_window,
)


async def _probe(label: str, url: str, params: dict, timeout: float) -> None:
    started = monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params)
        elapsed = monotonic() - started
        body = response.text or ""
        print(
            f"[{label}] status={response.status_code} elapsed={elapsed:.2f}s "
            f"bytes={len(body)}"
        )
        # 본문 앞부분만 노출(serviceKey는 params에만 있고 본문엔 없음).
        snippet = body.strip().replace("\n", " ")[:200]
        if snippet:
            print(f"[{label}] body_head={snippet}")
    except Exception as exc:  # noqa: BLE001 - 분류가 목적이므로 광범위 catch
        elapsed = monotonic() - started
        print(
            f"[{label}] FAILED after {elapsed:.2f}s -> "
            f"{type(exc).__module__}.{type(exc).__name__}: {exc!r}"
        )


async def main(stock_code: str, index_name: str, timeout: float) -> None:
    key_set = bool(settings.DATA_GO_KR_API_KEY)
    print(f"DATA_GO_KR_API_KEY configured: {key_set} (value not printed)")
    print(f"timeout per call: {timeout}s\n")

    window = _recent_basdt_window()
    await _probe(
        "stock",
        DATA_GO_STOCK_URL,
        _data_go_params({"numOfRows": 1, "likeSrtnCd": stock_code, **window}),
        timeout,
    )
    await _probe(
        "index",
        DATA_GO_INDEX_URL,
        _data_go_params({"numOfRows": 1, "idxNm": index_name, **window}),
        timeout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe data.go.kr reachability")
    parser.add_argument("--stock", default="005930", help="KR stock code (default: 005930)")
    parser.add_argument("--index", default="코스피", help="KR index idxNm (default: 코스피)")
    parser.add_argument("--timeout", type=float, default=25.0, help="per-call timeout seconds")
    args = parser.parse_args()
    asyncio.run(main(args.stock, args.index, args.timeout))
