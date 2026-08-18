# TODO

> 열린 결정·예정 작업. 완료되면 지운다 — 이 파일은 히스토리가 아니다.

## 열린 결정

- **`expo-image-picker` + `RECORD_AUDIO` 제거 여부** — 양쪽 다 src 사용 0건
  확인됨(2026-07-17). 네이티브 변경이라 다음 `v*` 빌드에 반영. 사진 업로드
  기능의 부활 계획에 달린 제품 결정.
- **`web/legal/terms.html` 큐레이션 문구** — 약관이 제거된 기능(큐레이션 피드)을
  서비스 내용으로 기술 중. 약관 개정 고지 의무 검토 필요.
- **은퇴 테이블 DROP** — `curations` · `curation_spots` · `plans` ·
  `travel_shorts` · `travel_shorts_spots`. 코드 참조는 제거됐으니 롤백 대상
  이미지가 교체된 뒤 별도 리비전으로
  (→ [ADR-0002](adr/0002-expand-contract-migrations.md)).
- **`users.taste_vector` 처리** — 계산하는 코드가 없다. 쓰기 경로는 탈퇴 시
  `= None` 하나뿐이고, 추천은 실제로 `user_saved_spots` 이웃 검색으로 돈다
  (`home.load_recommendations`). ivfflat 인덱스만 남아 있다. **그냥 매핑을 빼면
  탈퇴 사용자의 벡터가 남으므로**, 전량 NULL 백필 → 코드 참조 제거 → DROP 순서로.
- **`spot_moods` 재생성 경로** — 4,677행이 카테고리에서 결정적으로 파생된
  값인데 적재 코드가 레포에 없다. 신규 스팟은 agent `mood_search` 축에 영영
  안 걸린다. `lcls_systm*` → mood 매핑을 코드로 옮겨 `pipeline-daily` 에 붙일 것.
- **`image-validate` 판정 위치** — CT111 프로브는 tong CDN 엣지 차이로 삭제
  이미지도 200 을 본다(4.3만 장 전수 사망 0건). `img.pictrip.org` 경유 프로브 +
  Worker 폴백 마커 헤더로 바꾸거나, 잡을 접고 클라이언트 강등에 맡길 것.

## 예정

- **S14 대화형 일정 에이전트 v2** — `feat/plan-agent-v2`에서 재설계 진행 중.
  웹 플레이그라운드 선행, 앱 이식 후행. 머지 시 스펙을 이 문서 체계
  (explanation/how-to/reference/adr)로 편입한다.
- **매칭 임계값 재튜닝** — 갤러리 centroid 커버리지 수렴 후
  `MATCH_DISTANCE_MAX` 재평가.
- **assetlinks 지문** — `web/.well-known/assetlinks.json` placeholder를 실제
  Android 서명 지문으로 교체 (Android 릴리스 전).
