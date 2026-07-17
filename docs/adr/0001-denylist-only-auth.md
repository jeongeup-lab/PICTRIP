# 0001. 인증은 denylist 단일 모델 (fail-open)

- 상태: 채택
- 날짜: 2026-06-20
- 관련: `app/core/auth.py`, [data-model](../explanation/data-model.md)

## 맥락
초기 카카오 인증은 refresh 회전 + 도난탐지(rt:active/deny/grace, 세션·디바이스
테이블, 5-key Lua)로 over-engineering돼 있었다. 이 모델은 rt:active가
source-of-truth라 **단일 홈서버에서 Redis가 소실되면 전 사용자가 강제
로그아웃된다(fail-closed)**. access 토큰은 어차피 15분간 무검사라 도난탐지의
순이익도 미미했다.

## 결정
**로그아웃/탈퇴는 `denyjti:{jti}` 한 키만 SET하고, refresh는 JWT 검증 +
denylist EXISTS만 확인한다.** Redis 장애 시 fail-open — 폐기된 토큰이 잠시
살아나는 쪽을, 전원 로그아웃보다 낫다고 판단했다. 세션/디바이스 테이블과
refresh 회전은 폐기. access=메모리 15분, refresh=expo-secure-store 30일 슬라이딩.

## 고려한 대안
- **refresh 회전 + 도난탐지 유지** — 단일 서버 Redis 소실 = 전원 로그아웃.
  운영 비용 대비 보안 이득 미미. 기각.

## 결과
- 발급 시 Redis 쓰기 0. 로그아웃·탈퇴만 denylist SET.
- 세션 저장소 장애가 로그인 가용성에 영향을 주지 않는다.
