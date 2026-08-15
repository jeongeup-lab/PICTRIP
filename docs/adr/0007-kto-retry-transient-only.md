# 0007. KTO 재시도는 transient-only

- 상태: 채택
- 날짜: 2026-07-17
- 관련: `app/core/kto_client.py`, `pipeline/src/pictrip_data/kto/client.py`

## 맥락
backend `kto_client`는 모든 `HTTPStatusError`를 3회 재시도했다. 잘못된
serviceKey·파라미터 같은 비일시 4xx도 재시도되어 **KTO 일일 쿼터(실측
~1,000콜)를 성공 가능성 0인 호출로 태울 수 있었다**. pipeline은 이미
429·5xx만 재시도하는 정책이라 두 구현이 의미적으로 갈라져 있었다.

## 결정
**재시도는 실제 일시 오류만: HTTP 429·5xx, `TimeoutException`, `NetworkError`,
`RemoteProtocolError`.** 그 외(비일시 4xx, `UnsupportedProtocol` 같은 결정적
클라이언트 오류, 재시도가 실호출을 소모하는 `TooManyRedirects`·`DecodingError`)는
즉시 raise. backend·pipeline 동일 정책.

## 고려한 대안
- **`RequestError` 전체 재시도** — 결정적 설정 오류까지 3회 지연시키고 일부는
  쿼터를 소모. 기각 (리뷰 봇 P2 수용으로 축소).

## 결과
- `_is_transient` 단위 테스트가 양 프로젝트 정책을 고정한다.
- 429는 예외적으로 재시도한다 — 레이트리밋은 일시 상태다.
