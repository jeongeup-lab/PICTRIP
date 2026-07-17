# 용어집

> 이 문서는 PicTrip 전반에서 쓰는 용어를 정의한다. 코드 식별자와 함께 표기한다.

| 용어 | 정의 |
|---|---|
| **스팟** (`spot`, `contentId`) | KTO 국내 관광지 1건. `contentId`(문자열)가 canonical 키. |
| **해외 게시물** (`overseas_spot`) | Wikidata 유래 해외 명소 1건 — 피드의 hero. `wikidata_id` unique, `fame_score`로 정렬, `is_hidden`으로 모더레이션. |
| **매칭** (`match`) | 해외 게시물 임베딩과 국내 임베딩의 코사인 거리 ANN 상위 3곳. `MATCH_DISTANCE_MAX=0.32` 이내만. |
| **채널** (`channel`) | 홈 상단 타일 6종 — `around`(내 주변)·`hot`·`hidden`(집중률 기반)·`festa`·`pets`·`snap`(KTO 서비스 기반). |
| **집중률** (`spot_concentration`) | KTO TatsCnctrRateService의 상대 방문 집중도(0–100). Hot/Hidden 채널의 소스. |
| **갤러리 centroid** | 스팟 갤러리 최대 5장의 CLIP 임베딩 평균 — 대표사진 한 장의 편향(복권)을 완화. |
| **halfvec** | pgvector의 half-precision 벡터 타입. 임베딩 컬럼 전부 `halfvec(512)`. |
| **JSend 엔벨로프** | 모든 API 응답 형태 `{data, error, meta}`. `meta.traceId` 자동 주입. |
| **AppError 코드** | 에러 분기 계약. 모바일은 `err.code`로만 분기(`err.message` 금지). union은 `app-error.ts`와 동기. |
| **공공누리 Type1/Type3** (`cpyrhtDivCd`) | KTO 이미지 라이선스 구분. Type1=출처표시(변형 가능), Type3=변경금지(무변형 pass-through만). |
| **t1 변환** | `img.pictrip.org/t1/{width}/{sig}/…` — Type1 한정 HMAC 서명 서버측 리사이즈(폭 1620). |
| **워터마크 클리핑** | KTO 이미지 하단 ~12% 밴드를 프레임 밖으로 미는 클라이언트 CSS 프레이밍. 파일 무변형 — Type 구분과 무관. |
| **blur-up** | 미드사이즈를 블러 프리뷰로 먼저 그리고 본 이미지를 페이드인하는 로딩 패턴. |
| **seed** | 피드/탐색 셔플 키. 당겨서 새로고침 = 새 seed. |
| **denylist** (`denyjti:{jti}`) | 로그아웃·탈퇴된 refresh 토큰의 Redis 표식. fail-open(→ [ADR-0001](../adr/0001-denylist-only-auth.md)). |
| **centroid (지역)** | 시군구 중심좌표 — 사전계산 없이 spots mapx/mapy 런타임 AVG. |
| **watermark (sync)** | pipeline 증분 동기화의 `modifiedtime` 기준점. TEXT 원문으로 저장. |
| **expand→contract** | 추가 마이그레이션 먼저, 파괴적 변경은 무참조 확인 후 별도 리비전(→ [ADR-0002](../adr/0002-expand-contract-migrations.md)). |
| **fingerprint 가드** | EAS OTA가 네이티브 지문 일치 빌드에만 전달되는 안전장치. 네이티브 변경은 `v*` 태그로만 배포된다. |
| **바운스 (OAuth)** | 카카오가 커스텀 스킴을 거부해 `pictrip.org/oauthredirect`가 `pictrip://`로 재전송하는 우회. |

---
관련: [architecture](architecture.md) · [product](product.md) · [data-model](data-model.md)
