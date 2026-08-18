# 모니터링

두 스택으로 나뉜다. **지금 떠 있는 것은 CT111 Uptime-Kuma 뿐이다.**

| 경로 | 호스트 | 상태 |
|---|---|---|
| `uptime-kuma/` | CT111 | **운영 중** — DAG heartbeat + API HTTP 체크 |
| `docker-compose.yml` · `prometheus.yml` · `alert-rules/` · `grafana/` | (미배포) | Phase 3 — 마감 후 |

## Uptime-Kuma (CT111)

```bash
# CT111 에서
cd /opt/pictrip-monitoring && docker compose up -d
```

UI 는 tailnet 경유 `http://100.110.13.57:3001`. 퍼블릭 노출 없음.

| 모니터 | 종류 | 주기 | 시크릿 |
|---|---|---|---|
| `pipeline-daily` | Push | 108,000s (30h) | `KUMA_PUSH_PIPELINE_DAILY` |
| `pipeline-weekly` | Push | 691,200s (8d) | `KUMA_PUSH_PIPELINE_WEEKLY` |
| `api.pictrip.org` | HTTP | 300s | — |

주기는 잡 주기보다 넉넉히 길게 잡는다 — 잡이 실패해서 안 오는 것과 GitHub 이
스케줄을 늦게 디스패치한 것을 구분해야 한다.

**`pipeline-monthly` 는 Push 모니터가 없다.** Uptime-Kuma 1.x 의 하트비트 주기
상한이 **2,073,600초(24일)** 라, 30일 주기 잡은 매달 6일씩 거짓 down 이 된다.
알림 피로가 무알림보다 나쁘므로 만들지 않았다. 대안은 주간 DAG 에
`max(overseas_spots.updated_at) < 40일` 데이터 신선도 단언을 넣는 것 — `docs/todo.md`.

알림은 **ntfy**(`ntfy.sh`, 토픽은 서버 설정에만 존재 — 커밋 금지)로 나간다.
기본 알림 + 기존 모니터 전체 적용으로 설정돼 있다.

push 모니터가 잡는 것은 "잡이 실패했다" 뿐 아니라 **"아예 안 돌았다"** 이다.
2026-06-26~08-18 증분 수집이 54일간 no-op 이었는데 아무도 몰랐던 것이 이 잡을
세운 이유다(`sync_runs` 는 매일 success 로 기록됐다).

## Phase 3 (마감 후)

Prometheus + Grafana + Loki/Alloy. `prometheus.yml` 의 타깃(CT112 `/metrics`,
CT110 postgres_exporter 등)은 아직 exporter 가 없어 그대로는 뜨지 않는다.
