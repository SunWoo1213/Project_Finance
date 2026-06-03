# 배포 frontend에서 localhost backend 호출 차단 분석

Date: 2026-06-03
유형: 장애 원인 분석 (코드 변경 없음)

## 1. 증상

배포된 frontend(`https://finance-assist-gray.vercel.app`)에서 다음 콘솔 오류가 반복 발생한다.

```
Access to XMLHttpRequest at 'http://localhost:8000/api/market/prices'
from origin 'https://finance-assist-gray.vercel.app' has been blocked by CORS policy:
Permission was denied for this request to access the `loopback` address space.

localhost:8000/api/market/prices:1  Failed to load resource: net::ERR_FAILED
Failed to fetch market data: AxiosError: Network Error
```

영향 받는 호출은 `/api/market/prices`, `/api/market/news`, `/api/billing/plans` 등 frontend가 backend로 보내는 모든 요청이다. 결과적으로 시장 데이터, US/KR TOP 10, 채권, 원자재, 암호화폐, 요금제 화면이 전부 로드되지 않는다.

## 2. 핵심 원인 (두 가지가 겹쳐 있음)

### 원인 A — 배포 frontend가 backend 주소를 `http://localhost:8000`으로 보고 있다

frontend의 API base URL은 빌드 시점의 환경변수로 결정된다.

[frontend/src/utils/apiClient.js:3](frontend/src/utils/apiClient.js#L3)

```js
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
```

`VITE_` 변수는 런타임이 아니라 **빌드 시점에 번들에 박힌다**. Vercel 빌드에서 `VITE_API_BASE_URL`이 비어 있었기 때문에 fallback인 `http://localhost:8000`이 그대로 production 번들(`index-C7C_pyvY.js`)에 들어갔다.

따라서 배포 사이트를 여는 **방문자 브라우저**가 자기 PC의 `localhost:8000`을 호출하게 된다. 이는 배포된 backend가 아니라, 방문자 본인 컴퓨터의 8000 포트를 가리키므로 의도한 backend에 절대 닿지 못한다.

### 원인 B — 브라우저의 Private Network Access(loopback) 차단

오류 메시지의 핵심은 일반 CORS 거부가 아니라 다음 문구다.

```
Permission was denied for this request to access the `loopback` address space.
```

이는 Chromium 계열 브라우저의 **Private Network Access(PNA, 구 CORS-RFC1918)** 정책이다. 공개(public) HTTPS origin(`https://...vercel.app`)에서 **loopback 주소(`localhost`/`127.0.0.1`)** 로 향하는 요청은 보안상 기본 차단된다. 설령 backend가 CORS를 올바르게 열어 두었더라도, 공개 사이트 → loopback 방향 요청 자체가 브라우저 단에서 막힌다.

즉 원인 A로 잘못된 주소를 호출하고, 그 잘못된 주소가 하필 loopback이라서 원인 B의 차단까지 동시에 걸린 것이다. `net::ERR_FAILED`와 `AxiosError: Network Error`는 그 결과다.

## 3. 무엇이 원인이 아닌가

- backend의 CORS 설정이 잘못된 것이 **아니다**. 요청이 backend에 도달조차 못 했다(loopback 차단 + 존재하지 않는 대상). backend CORS([backend/app/main.py:288](backend/app/main.py#L288), `settings.cors_origins()` / `BACKEND_CORS_ORIGIN_REGEX`)는 이 증상의 직접 원인이 아니다.
- HTTPS/혼합 콘텐츠(mixed content) 문제로 오해하기 쉽지만, 메시지가 명시적으로 `loopback address space`를 가리키므로 PNA 차단이 1차 트리거다.

## 4. 해결 방향

### 4.1 필수: 배포 frontend가 실제 backend HTTPS origin을 가리키게 한다

1. backend를 공개 HTTPS origin으로 배포한다(예: `https://<backend-host>`). 현재 backend가 어디에 배포되어 있는지 먼저 확인이 필요하다.
2. Vercel 프로젝트 환경변수에 `VITE_API_BASE_URL=https://<backend-host>`를 등록한다(path 없이 scheme+host만).
   - 참고: [ENVIRONMENT_VARIABLE_SETUP.md](ENVIRONMENT_VARIABLE_SETUP.md) 4절 "Frontend public runtime", 14절 "배포 환경변수 등록".
3. `VITE_` 변수는 빌드 시 박히므로, 값 등록 후 **반드시 재배포(redeploy)** 해야 번들에 반영된다. 기존 빌드 캐시 재사용으로는 적용되지 않는다.

### 4.2 필수: backend CORS에 배포 frontend origin 허용

backend 환경변수에 다음을 등록한다.

```dotenv
BACKEND_CORS_ORIGINS=https://finance-assist-gray.vercel.app
```

Vercel preview URL이 매번 바뀌면 `BACKEND_CORS_ORIGIN_REGEX`로 패턴 허용을 검토한다(운영에서는 정확한 origin 목록 우선). 원인 A를 고치면 호출 대상이 공개 HTTPS backend가 되므로, 이때부터 backend CORS 허용이 실제로 의미를 가진다.

### 4.3 backend가 HTTPS 공개 주소를 가질 때 loopback 차단 자동 해소

원인 A를 고쳐 호출 대상이 `localhost`가 아니게 되면, 원인 B(loopback PNA 차단)는 더 이상 발생하지 않는다. PNA는 "공개 → loopback" 조합에서만 트리거되기 때문이다.

## 5. 검증 방법 (해결 후)

1. Vercel에서 `VITE_API_BASE_URL`을 backend HTTPS origin으로 설정하고 재배포한다.
2. 배포 사이트의 브라우저 Network 탭에서 요청 대상이 `localhost:8000`이 아니라 backend HTTPS origin으로 바뀌었는지 확인한다.
3. backend의 `/health`, `/db-check`가 배포 origin에서 정상 응답하는지 확인한다.
4. `/api/market/prices`, `/api/market/news`, `/api/billing/plans` 응답 상태 코드가 200인지 확인한다.
5. 응답 헤더에 `Access-Control-Allow-Origin`이 배포 frontend origin으로 내려오는지 확인한다.

## 6. 비밀값 주의

- 이 문서에는 실제 backend URL의 secret이나 API key, DB credential을 넣지 않았다.
- `VITE_API_BASE_URL`은 public 값이지만, backend secret을 `VITE_` 변수에 넣지 않는다.

## 7. 후속 위험 / 미실행 항목

- backend의 실제 배포 위치(공개 HTTPS origin 존재 여부)가 이 문서 작성 시점에 미확인 상태다. backend가 아직 공개 배포되어 있지 않다면, frontend 환경변수만 바꿔도 동작하지 않는다. backend 공개 배포가 선행되어야 한다.
- 코드 변경은 수행하지 않았다(원인 분석만). `apiClient.js`의 fallback `http://localhost:8000`은 로컬 개발용으로 의도된 값이므로 그대로 두는 것이 맞다. 수정 대상은 코드가 아니라 **배포 환경변수**다.
