# S12 — 옵저버빌리티 설계 (모니터링 · 로깅 · 에러트래킹 · 업타임 · 알림)

> 입력 SSOT: `session-context.md`, `CLAUDE.md`, **S08-infra**(토폴로지·Redis·헬스/
> 디스크), **현 옵저버빌리티(실측)** — `backend/app/core/{logging,middleware,error_handlers}.py`,
> `backend/app/main.py`(Sentry init), `backend/pyproject.toml`(deps), `deploy/homeserver/*`
> (pictrip-health.sh, cron), `backend/app/config.py`(SENTRY_* 설정).
> 외부 합의 근거: 셀프호스트/홈랩/소규모 옵저버빌리티 딥리서치(26 소스·130 클레임·25 적대검증,
> 2026-06-21). 검증 표기 — ✓=3표 통과, ✗=기각(함정), ⚠=약하게 기각.
> 설계 철학: S8과 동일 — **"이상 설계 → 현실 reconcile"**. 백지 아님, 15GB 단일 홈서버 기준.
> **풀스택 일괄 도입 금지 — 4기둥을 ROI 순으로 단계 적층.**

## 0. 요약 (확정 결정)

1. **4기둥 모델 + 단계 적층**: 에러트래킹 → 업타임 → 메트릭 → (로그) → (트레이스). 전부
   동시에 깔지 않는다. **공모전 1차 마감(2026-09-21 16:00 KST)까지는 Phase 0~2(~650MB)만으로
   충분**, 로그수집(Loki)·트레이싱(Tempo)은 마감 이후.
2. **에러트래킹 = Sentry SaaS 무료 플랜**(셀프호스트 기각). SDK·init 코드는 **이미 존재**
   (`main.py`, `SENTRY_DSN` 빈값이면 init 스킵) → **`.env`에 DSN 한 줄이면 켜짐**. 셀프호스트
   Sentry는 ~4GB+ RAM이라 15GB 호스트에 부적합. ✓ "DSN-only로 FastAPI 5xx 자동캡처".
3. **업타임 = Uptime Kuma 셀프호스트**. 현 Discord cron(`*/5`, **내부 IP** `/health`만 봄)을
   대체/보강 — 외부 `api.pictrip.org` HTTPS + **SSL 만기 경고** + 응답시간. ✗ "Kuma+Netdata면
   80% 커버"(메트릭 기둥은 Prometheus 필요)이므로 Kuma는 업타임 전용으로만 한정.
4. **메트릭 = Prometheus + Grafana + exporter 4종**(node/cAdvisor/postgres/redis) +
   FastAPI `/metrics`(RED). 전체 ~500MB. ✓ 표준 조합. ✗ "소규모엔 Prometheus 오버엔지니어링"
   (기각 — 가볍게 운영 가능, 특히 **디스크/RAM 알림**은 단일 호스트의 필수 안전장치).
5. **로그수집(Phase 3) = Loki + Grafana Alloy**. ⚠ **Promtail은 EOL → Alloy 사용**(옛 블로그
   추종 금지). 우리는 **이미 structlog JSON + traceId** → 라벨 파싱 즉시 가능, `traceId`로 요청
   전체 로그 검색. ✓ "Loki는 본문 아닌 라벨만 인덱싱 → ELK 대비 경량".
6. **트레이싱(Phase 4, 선택) = OTel + Tempo**, 멀티홉 디버깅이 실제로 아파질 때만. ✗ "OTel
   auto-instr 한 줄로 전 스택 커버"(기각 — 수동 계측 공수 실재). "쉽다" 가정 금지.
7. **호스트 배치**: 수집기/대시보드(Prometheus·Grafana·Loki·Kuma)는 **신규 경량 LXC
   `CT113 pictrip-mon`**(권장) — CT112(api, RAM 빡빡) 회피, CT111(juns 파이프라인) 비결합.
   node_exporter만 **pve 호스트**(비특권 LXC는 호스트 메트릭 못 봄). ✗ 검증 caveat 반영.

---

## 1. 현 옵저버빌리티 (실측) — 있는 것 / 빈칸

토대는 생각보다 좋다. **인스트루먼테이션(코드)은 상당부분 있고, 수집·저장·시각화(인프라)가 0.**

| 4기둥 항목 | 현 상태 | 실측 위치 / 비고 |
|---|---|---|
| 구조화 로깅 | ✅ 있음 | structlog, prod=JSONRenderer/local=Console (`core/logging.py`). **stdout으로만 → 어디에도 안 모임**(컨테이너 재시작 시 증발) |
| traceId 전파 | ✅ 있음 | `TraceIdMiddleware`가 요청마다 생성/전파, 모든 로그·응답헤더 주입 (`core/middleware.py`) |
| 요청 메트릭(로그) | ✅ 부분 | `request.completed`에 method/path/status_code/duration_ms (로그일 뿐, **집계·시계열 아님**) |
| 에러트래킹 | 🟡 설치·꺼짐 | `sentry-sdk[fastapi]` 설치됨, `main.py`에서 조건부 init — **`SENTRY_DSN` 빈값 → 스킵**. traces 0.1/profiles 0.05 샘플 기본 |
| `/health` | ✅ 있음 | JSend. S8 §2.2에서 **Redis PING 포함**으로 확장 예정(덴리스트 fail-open 가시화) |
| 외부 업타임 | 🟡 약함 | `pictrip-health.sh` cron `*/5` — **내부** `192.168.219.101:8000/health`만. 외부 가용성/SSL만기/터널다운 미감지. Discord 상태변화 알림(스팸방지 state파일) |
| `/metrics`(Prometheus) | ❌ 없음 | prometheus-client·instrumentator 미설치 |
| 호스트/컨테이너/DB/Redis 메트릭 | ❌ 없음 | **15GB 단일 디스크인데 RAM·디스크 감시 0** — 과거 torch 이미지 디스크풀로 배포실패 이력(재발 방지 시급) |
| 로그 중앙수집 | ❌ 없음 | Loki/Alloy 없음 |
| 분산 트레이싱 | ❌ 없음 | OTel/Tempo 없음 |

- **AWS 잔재 정리 대상**: `logging.py` 주석 "CloudWatch용 JSON"은 AWS 시절 흔적(현재 AWS 없음).
  동작 무해, 문구만 정리.
- **실제 빈칸 우선순위**: ① Sentry 켜기(거의 공짜) ② 진짜 외부 업타임 ③ **리소스 메트릭/알림
  (디스크풀 재발 방지)** ④ 로그 중앙화.

---

## 2. 설계 원칙 — 4기둥 + 업계 합의(검증 결과)

옵저버빌리티를 4개로 쪼개고 **ROI 순으로 적층**한다(동시 도입 금지). 아래는 딥리서치가 적대
검증으로 통과/기각한 사실들 — **기각된 통념이 곧 함정 경고.**

| 기둥 | 무엇 | 표준 도구 | PicTrip 단계 |
|---|---|---|---|
| 에러트래킹 | 예외·스택트레이스·릴리즈별 회귀 | **Sentry** | Phase 0 |
| 업타임 | 외부 가용성·SSL 만기 | **Uptime Kuma** | Phase 1 |
| 메트릭 | RED + 호스트/컨테이너/DB/Redis 리소스 | **Prometheus + Grafana** | Phase 2 |
| 로그수집 | stdout 중앙 검색 | **Loki + Grafana Alloy** | Phase 3 |
| 트레이싱 | 분산 추적(멀티홉) | OTel + Tempo | Phase 4(선택) |

**검증 통과(✓, 채택 근거):**
- Sentry는 **DSN만으로 FastAPI 5xx/예외 자동 캡처** — 최소 설정 에러트래커. (docs.sentry.io)
- 표준 메트릭 스택 = `/metrics`(RED) + `postgres_exporter:9187` + `redis_exporter:9121` +
  `cAdvisor:8080` → Prometheus → Grafana, **~500MB RAM**. (grafana RED method, prom-community)
- **Prometheus가 사실상 표준 TSDB**, 자체 TSDB 보유 + remote-write로 오프로드 가능.
- **Loki는 본문 아닌 라벨만 인덱싱** → 동급 로그량에서 ELK/OpenSearch보다 경량. (grafana/loki)
- **OTel로 trace_id를 로그에 주입 → 로그↔트레이스 연결**(LGTM 통합 핵심).
- **Docker stdout 로그는 로깅 드라이버로 수집**(앱 수정 불필요).
- **Netdata는 zero-config·로컬 우선** 실시간 대시보드 — 단 장기보존·알림룰·DB내부메트릭 부족.

**검증 기각(✗/⚠, 함정 경고):**
- ✗ "OTel auto-instr이 패키지+`instrument_app()` 한 줄로 FastAPI·SQLAlchemy·asyncpg·Redis·
  httpx 전부 커버" (0-3). **트레이싱을 '쉽다'고 먼저 깔지 말 것.**
- ✗ "소규모 팀은 Kuma+Netdata면 80% 커버" (0-3). **메트릭 기둥은 Prometheus가 필요.**
- ✗ "2~3대엔 Prometheus 풀스택은 오버엔지니어링/2GB 필수" (0-3). **소규모라고 스킵 금지, 더
  가볍게 운영 가능.**
- ⚠ "홈랩은 멀티홉 없으니 Tempo 스킵" (1-2). 트레이싱도 가치는 있음 — 단 우선순위 최하.

**미해결(도입 시 짧게 PoC/결정):**
- **VictoriaMetrics vs Prometheus** — VM이 호환·더 경량. 15GB 빡빡하면 Phase 2에서 대안 검토.
- node_exporter 세부 배치(아래 §4에서 pve 호스트로 확정).
- Sentry SaaS vs 셀프호스트 → **SaaS 확정**(셀프호스트 ~4GB+, 호스트 부적합).

---

## 3. 단계별 도입안 (체크리스트)

각 Phase는 독립 배포 가능. 누적 RAM은 §4. **Phase 0~2가 비용 대비 효과의 ~90%.**

### Phase 0 — 오늘 당장 (추가 RAM ≈ 0)
가장 ROI 높고 거의 공짜. 솔로 개발에서 "사용자가 말하기 전에 먼저 안다"의 핵심.
- [ ] Sentry SaaS 프로젝트 생성 → `SENTRY_DSN`을 CT112 `/opt/pictrip-api/.env`에 추가(불가침
      `.env` 규칙: `.deploy.env` 아님 본 `.env`). 재배포 시 자동 init. (코드 변경 0)
- [ ] Sentry `environment=production`, `release`=배포 SHA 연동(이미 `ENVIRONMENT` 전달, release만
      추가 검토) → 릴리즈별 회귀 추적.
- [ ] **Docker 로그 로테이션** — compose(api·redis)에 `logging: json-file, max-size: 10m,
      max-file: 3`. (stdout 로그 디스크 잠식 차단 — 디스크풀 예방)
- [ ] 임시 외부 업타임 — UptimeRobot 무료로 `https://api.pictrip.org/health` 5분 감시(Phase 1에
      셀프호스트로 대체).
- [ ] `logging.py` "CloudWatch" 주석 정리(AWS 잔재).

### Phase 1 — 업타임 + 알림 (추가 RAM ≈ +150MB)
- [ ] **Uptime Kuma**(Docker, ~100~150MB) on CT113. 모니터: `api.pictrip.org/health`(외부 HTTPS),
      apex `pictrip.org`(CF Pages), 필요 시 keyword(`"status":"ok"`).
- [ ] **SSL 인증서 만기 경고**(Kuma 기본 — 터널/CF 인증서 만기 사전 경보).
- [ ] 알림 채널 = **Discord 재사용**(기존 webhook) 또는 **ntfy/gotify 폰 푸시** 추가.
- [ ] 현 `pictrip-health.sh` cron 은퇴/축소(Kuma가 외부+상태변화 모두 커버; 내부 probe는 백업으로
      유지 선택).

### Phase 2 — 메트릭 + 대시보드 (추가 RAM ≈ +500MB) ★최우선 실효
- [ ] `prometheus-fastapi-instrumentator` 추가 → `/metrics` 노출(RED: 요청율·에러율·지연
      p50/p95/p99). 앱 코드 최소 변경. (pyproject deps + main.py 1~2줄)
- [ ] **exporter 배치**(§4): node_exporter→**pve 호스트**, cAdvisor→**CT112**,
      postgres_exporter→**CT110**(LAN), redis_exporter→**CT112**.
- [ ] **Prometheus**(CT113) — scrape `/metrics`·4 exporter. 보존 **15~30일**(RAM/디스크 절약).
- [ ] **Grafana**(CT113) — 대시보드: ① RED(API) ② 호스트(CPU/RAM/**디스크%**) ③ Postgres
      (커넥션·캐시히트·느린쿼리) ④ Redis(메모리·키스페이스) ⑤ 컨테이너(cAdvisor).
- [ ] **알림룰**(Grafana/Alertmanager → Discord/ntfy): 디스크 >85%, RAM >90%, API 5xx 급증,
      p95 지연 임계, Redis maxmemory 근접, Postgres 커넥션 포화.
- [ ] *(선택)* 15GB 압박 시 Prometheus → **VictoriaMetrics**로 PoC 교체 검토.

### Phase 3 — 로그 중앙화 (추가 RAM ≈ +250MB, 마감 이후)
- [ ] **Loki + Grafana Alloy**(Promtail 아님) on CT113. Alloy가 CT112 docker stdout(JSON) 수집.
- [ ] 이미 **JSON + traceId** → 라벨 추출(level/path/status/traceId) 즉시. Grafana에서 `traceId`로
      요청 전체 로그 검색, 메트릭 이상 → 동일 Grafana에서 로그 드릴다운.
- [ ] Loki 보존기간·청크 압축 설정(경량 유지).

### Phase 4 — 트레이싱 (선택, 멀티홉이 아플 때만)
- [ ] CT111 파이프라인↔API↔DB 추적 필요 시 **OTel + Tempo**. ⚠ auto-instr "한 줄" 가정 금지 —
      수동 계측·검증 공수 산정 후 착수. trace_id를 기존 structlog 컨텍스트와 결선(로그↔트레이스).

---

## 4. 컴포넌트 배치 토폴로지 + RAM 예산

```
  ┌──────────────────────── Proxmox 홈서버 (Intel N100 / 15GB / 단일디스크) ───────────┐
  │                                                                                     │
  │  pve 호스트 ── node_exporter:9100  (호스트 CPU/RAM/디스크 — LXC에선 못 봄)          │
  │                                                                                     │
  │  CT112 pictrip-api                CT110 pictrip-db          CT113 pictrip-mon (신규) │
  │  ├─ api  → /metrics (RED)         ├─ Postgres              ├─ Prometheus  (~250MB)  │
  │  ├─ redis_exporter:9121           └─ postgres_exporter      ├─ Grafana     (~150MB)  │
  │  ├─ cAdvisor:8080  (~120MB)          :9187                  ├─ Uptime Kuma (~120MB)  │
  │  └─ (api·redis·tunnel·runner)                               ├─ Loki        (~180MB)*  │
  │                                   CT111 pictrip-pipeline    └─ Alloy       (~100MB)*  │
  │                                   (juns, 비결합)            (* = Phase 3)            │
  └─────────────────────────────────────────────────────────────────────────────────────┘
     Prometheus가 위 모든 exporter·/metrics 를 LAN으로 scrape → Grafana 시각화/알림
```

- **CT113 신규 경량 LXC 권장**(대안: CT111 동거). 사유: CT112는 torch 이미지+redis+runner로 RAM
  빡빡, CT111은 juns 파이프라인이라 비결합 유지. mon LXC ~1.5GB 할당이면 Phase 2까지 여유.
- **node_exporter는 pve 호스트에**(비특권 LXC 안에선 호스트 전체 리소스 불가시 — 검증 caveat).
- **postgres_exporter는 CT110**(locality) 또는 CT113에서 LAN 접속 — 둘 다 가능, CT110 권장.
- exporter는 무시할 RAM(각 ~20-50MB). cAdvisor만 상대적으로 큼(~120MB).

| 단계 | 추가 RAM | 누적 | 마감 전 필수 |
|---|---|---|---|
| Phase 0 (Sentry·로테이션·임시업타임) | ~0 | ~0 | ✅ 필수 |
| Phase 1 (Uptime Kuma) | ~150MB | ~150MB | ✅ 권장 |
| Phase 2 (Prom+Grafana+exporters) | ~500MB | ~650MB | ✅ 권장(디스크 알림) |
| Phase 3 (Loki+Alloy) | ~250MB | ~900MB | ⬜ 이후 |
| Phase 4 (OTel+Tempo) | ~300MB+ | ~1.2GB | ⬜ 필요 시 |

→ 풀스택 ~1.2GB로 15GB 중 충분. **Phase 0~2(~650MB)에 효과의 ~90% 집중.**

---

## 5. 알림 정책 (조용한 실패 → 시끄러운 알림)

S8 §2.2의 "fail-open을 시끄러운 알림으로 전환" 원칙을 옵저버빌리티 전역으로 확장.

| 신호 | 출처 | 채널 | 임계 |
|---|---|---|---|
| API 다운/SSL 만기 | Uptime Kuma | Discord/ntfy | 외부 probe 실패 / 만기 ≤14일 |
| 미처리 예외·5xx 급증 | Sentry | Sentry 메일/Discord | 신규 이슈 / 스파이크 |
| 디스크 >85% | node_exporter→Grafana | Discord/ntfy | 단일 디스크 — **최우선** |
| RAM >90% / OOM 위험 | node·cAdvisor | Discord/ntfy | torch 이미지 메모리 |
| Redis maxmemory 근접 | redis_exporter | Discord | S8 `maxmemory 256mb` noeviction |
| Postgres 커넥션 포화/느린쿼리 | postgres_exporter | Discord | 커넥션 한도·p95 |
| **Redis PING 실패** | `/health`(S8 §2.2) | Discord | 덴리스트 fail-open 갭 가시화 |

- 알림은 **상태변화·임계 돌파시에만**(현 health.sh state파일 철학 유지) — 스팸 방지.
- 채널 단일화: 기존 Discord webhook 재사용 + 폰 즉시성 필요 항목만 ntfy/gotify.

---

## 6. reconcile 노트 (현 상태 ↔ S12)

| 항목 | 현 상태 | 신규(S12) | 작업 위치 |
|---|---|---|---|
| 에러트래킹 | SDK 설치·DSN 빈값(꺼짐) | **DSN 주입으로 ON** | Phase 0 — CT112 `.env` |
| 로그 | structlog JSON stdout(휘발) | (Phase 3) Loki+Alloy 중앙수집 | 마감 이후 |
| `/health` | status만 | **+Redis PING**(S8 §2.2와 동일) | S10 구현과 합류 |
| 외부 업타임 | 내부 cron `*/5` | **Uptime Kuma**(외부+SSL) | Phase 1 |
| 메트릭 | 없음 | `/metrics`+exporter4+Prom+Grafana | Phase 2 |
| 호스트 감시 | 없음 | node_exporter(pve)+디스크 알림 | Phase 2 — **디스크풀 재발 방지** |
| 로그 로테이션 | 미설정(추정) | compose `max-size/max-file` | Phase 0 |
| mon LXC | 없음 | **CT113 pictrip-mon** 신규 | Phase 1~2 배포 |
| Discord health.sh | cron 스크립트 | Kuma로 대체/축소 | Phase 1 |
| "CloudWatch" 주석 | AWS 잔재 | 문구 정리 | Phase 0 |

**핵심**: 신규 *인프라 컴포넌트*는 mon LXC(CT113) 하나 + exporter들. 인스트루먼테이션(로그·
traceId·Sentry SDK)은 이미 코드에 있어 **켜거나 1~2줄 추가** 수준. S8과 충돌 없음 — S8의 Redis
PING/Discord 헬스 알림 파이프를 S12가 흡수·확장.

## 7. 후속 위임
- exporter/compose/CT113 **구현 + 배포 순서** = S10(또는 별 인프라 트랙).
- `/metrics` 라우트·`/health` Redis PING **API 형식** = S9 연계.
- Sentry `release`↔배포 SHA 연동 디테일 = CI/CD(backend-deploy.yml) 후속.
- VictoriaMetrics 대안 PoC = Phase 2 착수 시 결정(미해결).
- 트레이싱(OTel+Tempo) 상세 = Phase 4로 보류(마감 이후, 멀티홉 실수요 시).
