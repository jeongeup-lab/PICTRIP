# 임베딩 운영

> 목표: 임베딩 커버리지를 유지하고, 이미지 변경·백로그를 매칭 품질 저하 없이 처리한다.

## 전제
- 스크립트는 **:8000을 서빙 중인 라이브 api 컨테이너에 exec**한다 — 새 컨테이너를
  띄우지 않는다(이미지·`.env`·CT110 라우트를 이미 가진 유일한 곳).
- 임베딩 잡은 `admin:embed:running` Redis 락(4h)을 공유한다 — 동시 실행 불가.

## 단계

1. **커버리지 확인** — 어드민 콘솔 `/admin` 개요 카드, 또는:
   ```sql
   SELECT (SELECT count(*) FROM spot_embeddings) AS rep,
          (SELECT count(*) FROM spot_embeddings_gallery) AS gallery,
          (SELECT count(*) FROM embedding_failures) AS failures;
   ```

2. **대표사진 백필** — `backend-backfill-embeddings.yml` dispatch(기본 dry-run).
   사전조건: api 컨테이너 정확히 1개·healthy·마이그레이션 0019 적용.
   ```bash
   gh workflow run backend-backfill-embeddings.yml -f write=true
   ```

3. **image-validate 연쇄 처리** — 주간 `image-validate.yml`이 죽은 원본을
   교체(rewritten>0)하면 DB 트리거가 해당 임베딩을 삭제하고 `source_changed`로
   큐잉한다. **후속 백필을 돌려야 매칭이 복귀한다**:
   ```bash
   gh workflow run backend-backfill-embeddings.yml -f write=true   # --only-failed source_changed 경로
   ```

4. **갤러리 centroid** — 일일 크론(`gallery-backfill.yml`, 06:00 KST, 800스팟/일)이
   KTO 쿼터 안에서 자동 소진한다. 수동 킥은 dispatch로.

5. **해외 임베딩** — 월간 `overseas-sync.yml`의 embed 잡이 자동 수행.
   수동: 컨테이너에서 `python -m scripts.embed_overseas`.

## 검증
- `embedding_failures` count가 줄었는지, 어드민 개요의 진행률.
- 매칭 스팟체크: `GET /overseas/{id}/matches`가 3건을 반환.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| 트리거 버튼 409/거부 | 락 점유(이미 실행 중) | 4h TTL 대기 또는 완료 확인 |
| 백필이 곧장 끝남 | 백로그 0(정상) | resumable — no-op이 맞다 |
| KTO 429 다발 | 일일 쿼터(~1k) 소진 | 익일 자정 리셋 후 재개(크론 산식은 800/일로 여유 설계) |

---
관련: [data-model](../explanation/data-model.md) · [crons-and-workflows](../reference/crons-and-workflows.md) · [cli](../reference/cli.md)
