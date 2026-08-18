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
   사전조건: api 컨테이너 정확히 1개·healthy·alembic head 적용.
   ```bash
   gh workflow run backend-backfill-embeddings.yml -f write=true
   ```

3. **image-validate 연쇄** — 주간 `pipeline-weekly.yml` 이 죽은 원본을 교체하면
   DB 트리거가 해당 임베딩을 지우고 `source_changed` 로 큐잉한다. **후속 백필은
   같은 DAG 의 `embed-repair` 잡이 자동 수행**한다(`--only-failed --failure-reason
   source_changed`) — 예전처럼 사람이 dispatch 할 필요가 없다.

4. **신규 스팟** — 일일 `pipeline-daily.yml` 의 `embed` 잡이 `sync-kto` 뒤에 붙어
   `--limit 1000` 안에서 채운다. 백로그가 크면 며칠에 걸쳐 소진된다; 급하면
   `backend-backfill-embeddings.yml` 을 `write=true` 로 킥한다.

5. **갤러리 centroid** — `pipeline-weekly.yml` 의 `gallery-repair` 잡
   (`image-validate` 뒤, 800스팟/회). 전량 적재 후에는 사실상 no-op 이다.

6. **해외 임베딩** — 월간 `pipeline-monthly.yml` 의 `embed` 잡이 자동 수행.
   수동: 컨테이너에서 `python -m scripts.embed_overseas`.

> 임베딩 잡 3종은 `admin:embed:running` 락을 공유하므로 job-level
> `concurrency: embedding-job` 으로 워크플로를 가로질러 직렬화된다. 겹쳐 보이면
> 뒤에 온 잡이 pending 인 것이지 실패가 아니다.

## 검증
- `embedding_failures` count가 줄었는지, 어드민 개요의 진행률.
- 매칭 스팟체크: `GET /overseas/{id}/matches`가 3건을 반환.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| 트리거 버튼 409/거부 | 락 점유(이미 실행 중) | 4h TTL 대기 또는 완료 확인 |
| 백필이 곧장 끝남 | 백로그 0(정상) | resumable — no-op이 맞다 |
| 잡이 pending 에서 안 움직임 | `embedding-job` 동시성 그룹 대기 | 앞 잡이 끝나면 자동 진행 |
| KTO 429 다발 | 일일 쿼터(~1k) 소진 | 익일 자정 리셋 후 재개(크론 산식은 800/일로 여유 설계) |

---
관련: [data-model](../explanation/data-model.md) · [crons-and-workflows](../reference/crons-and-workflows.md) · [cli](../reference/cli.md)
