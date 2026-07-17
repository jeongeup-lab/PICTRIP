# 모바일 앱 실행

> 목표: 시뮬레이터에서 앱을 띄워 변경을 눈으로 확인하고, 푸시 전 스위트를 그린으로 만든다.

## 전제
- `mobile/`에서 `npm install` 완료. `node_modules`가 자기참조 심링크로 깨져
  있으면(체크아웃 직후 "too many levels of symbolic links") 지우고 재설치한다.
- 로컬 API를 쓰려면 Metro 시작 전 `EXPO_PUBLIC_API_BASE_URL`을 지정한다
  (미지정 시 `env.ts` 폴백 = 프로드 `https://api.pictrip.org/v1`).

## 단계

1. **개발 실행**
   ```bash
   cd mobile
   npx expo start            # 시뮬레이터에서 i (iOS)
   # 로컬 백엔드로: EXPO_PUBLIC_API_BASE_URL=http://localhost:8000/v1 npx expo start --clear
   ```

2. **푸시 전 검증 (전부 통과 필수)**
   ```bash
   npm run lint && npm run typecheck && npm run format:check && npm test
   ```

3. **Release 동작 확인이 필요할 때** — 시뮬 설치본은 임베디드 번들을 쓰므로
   Metro 변경이 반영되지 않는다. `expo run:ios --configuration Release`로 빌드한
   번들 산출물을 `.app`에 복사 후 재실행해야 실제 배포 동작을 본다.

4. **시뮬 위치** — 지도 흐름 확인은 GPS 세팅이 선행이다:
   ```bash
   xcrun simctl location booted set 37.5665,126.9780   # 서울시청
   ```

## 검증
- lint 0 errors(테스트 파일 require 경고 6건은 기존), tsc 통과, jest 전 suite green.
- 홈 피드가 카드를 그리고 스와이프 시 매칭 3장이 뜬다.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| 전 화면 API 404 | 빌드에 `EXPO_PUBLIC_API_BASE_URL` 미인라인 + 폴백 경로 문제 | 오리진 로그에서 `/v1` 없는 404 확인이 진단 기준 |
| 카카오/구글 로그인 실패 | `EXPO_PUBLIC_*` 키 미주입 | eas.json env 확인(→ [deploy-and-release](deploy-and-release.md)) |
| 지도 빈 화면 | SDK 로드 실패 | RN 오버레이의 HTTP 상태 확인(동적 로드 재프로브가 표시) |
| 네이티브 모듈 에러 | 새 네이티브 dep 추가 | 금지 — Expo SDK 56 핀 유지(`CLAUDE.md`) |

---
관련: [deploy-and-release](deploy-and-release.md) · [product](../explanation/product.md)
