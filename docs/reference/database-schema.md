# DB 스키마 레퍼런스

> 테이블·Redis 키의 조회용 표. 정본은 Alembic 히스토리(현 head `0020`).
> 개념·소유권 설명은 [data-model](../explanation/data-model.md).

## 테이블 (PostgreSQL + pgvector, CT110)

스키마 소유는 전부 backend Alembic(예외: `sync_runs`). "적재" = 데이터를 쓰는 주체.

| 테이블 | 적재 | 요지 |
|---|---|---|
| `spots` | pipeline (일일) | KTO 마스터. `show_flag=1` 부분 인덱스 다수 · `cpyrht_div_cd` CHECK(Type1/Type3) · `idx_spots_image_pool` |
| `spot_details` | backend (lazy) | detail* 7일 캐시. **`overview`는 여기, verbatim** |
| `spot_images` | backend (lazy) | detailImage2 URL만 (bytes 금지) · (content_id, sort_order) unique |
| `spot_embeddings` | backend 잡 | 대표사진 CLIP `halfvec(512)` · HNSW(halfvec_cosine, m/ef=0005와 일치 필수) |
| `spot_embeddings_gallery` | backend 잡 | 갤러리 ≤5장 centroid · 0020 트리거가 이미지 변경 시 행 삭제 |
| `embedding_failures` | backend 잡 | 재시도 큐 (`reason`, `--only-failed` 대상) |
| `overseas_spots` | pipeline (월간) | 해외 게시물. `wikidata_id` unique · `fame_score` · `is_hidden`(admin 토글) · embedding HNSW · 0019 트리거 |
| `spot_concentration` | 일일 크론 | 집중률 0–100 — Hot/Hidden 채널 소스 |
| `users` | backend | `taste_vector halfvec(512)` · email 부분 unique(`deleted_at IS NULL`) |
| `user_auth_providers` | backend | provider CHECK(kakao/google/apple/email) · (provider, provider_user_id) unique |
| `user_consents` | backend | `notification_consent` 컬럼은 의도적 unmapped |
| `user_saved_spots` | backend | (user_id, content_id) PK · 양방향 CASCADE |
| `admin_users` | 수동 | 콘솔 자격증명 (bcrypt) |
| `moods` · `spot_moods` · `regions` · `sigungus` · `lcls_systm_codes` | 시드/pipeline | 마스터 코드 |
| `sync_runs` | **pipeline 소유** | backend는 raw SQL read-only. **backend Alembic 추가 금지** |
| `curations` · `curation_spots` | — | 은퇴 자산. ORM 없음 — autogenerate `include_object` 제외로 보존 |

- 벡터 리터럴: `... <=> $1::halfvec(512)`.
- `hnsw.ef_search=80` — `app/core/db.py` asyncpg `server_settings`.

## Redis 키 (CT112)

AOF everysec + RDB · `noeviction` 256mb. 전부 재계산 가능한 캐시.

| 패턴 | TTL | 용도 |
|---|---|---|
| `denyjti:{jti}` | refresh 잔여 수명 | 로그아웃/탈퇴 denylist (**fail-open**) |
| `rl:{bucket}:{ip}` | 60s | rate-limit 카운터 (fail-open) |
| `spotdetail:v1:{contentId}` | 1h | 상세 응답 hot front |
| `rlte:{contentId}` | 1h | 연관 관광지 (Redis 전용 — 테이블 없음) |
| `match:{revision}:{overseasId}` | 6h | 매칭 결과 — `matching:revision` incr로 전체 무효화 |
| `channel:{key}:{version}` | KTO 채널 3d / 집중률 1h | 홈 채널 카드 |
| `region:{lat:.3f}:{lng:.3f}` | 1d | Kakao 역지오코딩 (null 캐시 포함) |
| `regions:tree` | 24h | 시도·시군구 트리 |
| `admin:embed:running` | 4h | 재임베딩 잡 분산 락 (SET NX) |

---
관련: [data-model](../explanation/data-model.md) · [api](api.md) · [ADR-0002](../adr/0002-expand-contract-migrations.md)
