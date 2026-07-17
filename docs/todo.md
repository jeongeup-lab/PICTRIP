# TODO

> 열린 결정·예정 작업. 완료되면 지운다 — 이 파일은 히스토리가 아니다.

## 열린 결정

- **`expo-image-picker` + `RECORD_AUDIO` 제거 여부** — 양쪽 다 src 사용 0건
  확인됨(2026-07-17). 네이티브 변경이라 다음 `v*` 빌드에 반영. 사진 업로드
  기능의 부활 계획에 달린 제품 결정.
- **`web/legal/terms.html` 큐레이션 문구** — 약관이 제거된 기능(큐레이션 피드)을
  서비스 내용으로 기술 중. 약관 개정 고지 의무 검토 필요.
- **`pipeline-sync.yml` 배선 (A7)** — admin "수집 즉시 실행" 버튼의 메커니즘
  확정(workflow_dispatch vs 대안) + 시크릿 주입.

## 예정

- **S14 대화형 일정 에이전트 v2** — `feat/plan-agent-v2`에서 재설계 진행 중.
  웹 플레이그라운드 선행, 앱 이식 후행. 머지 시 스펙을 이 문서 체계
  (explanation/how-to/reference/adr)로 편입한다.
- **매칭 임계값 재튜닝** — 갤러리 centroid 커버리지 수렴 후
  `MATCH_DISTANCE_MAX` 재평가.
- **assetlinks 지문** — `web/.well-known/assetlinks.json` placeholder를 실제
  Android 서명 지문으로 교체 (Android 릴리스 전).
