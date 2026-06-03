"""로그·예외 문자열에서 외부 API 키 등 민감 쿼리 파라미터를 마스킹한다.

`httpx` 예외(`HTTPStatusError` 등)의 메시지에는 요청 URL이 그대로 포함되며,
이 URL의 쿼리스트링에 Finnhub token, 공공데이터포털 `serviceKey`, Stooq `apikey`,
FRED `api_key` 등이 평문으로 들어 있다. 애플리케이션 로거가 이 예외를 그대로
출력하면(`%r`/`%s`) 시크릿이 로그에 남으므로, 로깅 직전에 이 헬퍼로 값을 가린다.
`httpx`/`sqlalchemy` 로거 레벨 조정으로는 막히지 않는 애플리케이션 레벨 누수를 차단한다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# serviceKey/apikey/api_key/token/key/auth/access_token/secret 등 쿼리 파라미터 값을 가린다.
_SENSITIVE_QUERY_PARAM = re.compile(
    r"(?i)([?&](?:serviceKey|api[_-]?key|apikey|token|auth|access[_-]?token|secret|key|password|pwd)=)[^&\s'\"]+"
)


def redact_secrets(value: object, extra_secrets: Iterable[str] | None = None) -> str:
    """문자열로 변환한 뒤 민감 정보를 ``***``로 치환한다.

    - 쿼리스트링의 민감 파라미터 값(``?serviceKey=...`` 등)을 가린다.
    - ``extra_secrets``로 넘긴 리터럴 시크릿(예: URL **경로**에 박히는 ECOS API 키)도
      문자열 어디에 있든 그대로 치환한다. 빈 값/짧은 값은 무시한다.
    """
    text = str(value)
    text = _SENSITIVE_QUERY_PARAM.sub(r"\1***", text)
    if extra_secrets:
        for secret in extra_secrets:
            if secret and len(str(secret)) >= 4:
                text = text.replace(str(secret), "***")
    return text
