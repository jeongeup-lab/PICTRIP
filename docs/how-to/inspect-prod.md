# 프로드 점검

> 목표: SSH 셸 없이(또는 최소로) 프로드 로그·DB·자격증명을 안전하게 다룬다.

## 전제
- GitHub Actions dispatch 권한. 직접 셸이 필요하면 `ssh root@100.83.101.1`(pve)
  → `pct exec <CT번호>`.
- 프로드 DB에 로컬 asyncpg 직결 금지 — `.env` 암호는 local-only다.

## 단계

1. **API 로그 grep** — 러너 경유, 셸 인젝션 방지를 위해 pattern은 env 전달:
   ```bash
   gh workflow run backend-logs.yml -f pattern='GET /v1/feed' -f since=6h
   ```

2. **소셜 로그인 거부 원인** — OIDC 검증 라인만(토큰/PII 없음):
   ```bash
   gh workflow run backend-oidc-logs.yml -f since=24h
   ```

3. **DB 읽기** (read-only):
   ```bash
   ssh root@100.83.101.1
   pct exec 110 -- docker exec -it pictrip-postgres psql -U pictrip pictrip
   ```

4. **admin 콘솔 자격증명 로테이션** — env가 아니라 `admin_users` 테이블이다.
   시드 기본(`admin`/`admin`)은 반드시 교체:
   ```bash
   # CT112 라이브 api 컨테이너에서
   python -m scripts.set_admin_password --username admin
   ```

5. **헬스 개요** — `https://api.pictrip.org/health`(liveness),
   `/admin/health`(컴포넌트별 — DB 다운 시에도 500 대신 degrade로 표시된다).

## 검증
- 로그 워크플로 출력의 count/샘플이 기대와 일치.
- 로테이션 후 구 자격증명으로 `/admin/login`이 거부된다.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| HOT/HIDDEN 채널 느림·이미지 없음 | DB가 아니라 CF 터널 RTT·Commons 429(실측 결론) | 엣지 캐시 워밍 상태 확인, DB 인덱스 의심 금지 |
| `/admin/login` 반복 실패 | 5회/분/IP 레이트리밋 | 1분 대기 |
| 시크릿 수정이 반영 안 됨 | `.env`는 :ro 마운트 | CT112에서 `docker restart` |

---
관련: [crons-and-workflows](../reference/crons-and-workflows.md) · [deploy-and-release](deploy-and-release.md) · [admin-console](../reference/admin-console.md)
