# 결정 기록

> 지금 살아 있는 결정과 그 근거. **현행만 적는다** — 뒤집힌 결정은 지우고,
> 왜 뒤집혔는지는 새 항목의 근거에 흡수한다. 전문(全文)과 당시 맥락은 git
> 히스토리에 있다(`git log --diff-filter=D -- docs/adr/`).
>
> 새 결정은 이 파일 맨 아래 표에 한 줄로 추가하고, 근거가 한 줄로 안 담기면
> 아래 **상세** 절에 붙인다. PR 본문의 `## 핵심 결정` 과 같은 내용이면 그쪽을
> 정본으로 삼고 여기엔 링크 없이 요지만 남긴다.

## 살아 있는 결정

| # | 날짜 | 결정 | 근거 (한 줄) | 코드 |
|---|---|---|---|---|
| 1 | 2026-06-11 | **지도는 WebView + Kakao JS SDK 단일 구현** | `@react-native-kakao/map` 은 Android 미구현·iOS 시뮬 blank 이고, 네이티브 모듈이 Expo SDK 56 핀 트리를 깨뜨린다 | `mobile/src/features/map/components/KakaoWebMap.tsx` |
| 2 | 2026-06-20 | **인증은 denylist 단일 모델, fail-open** | refresh 회전+도난탐지는 `rt:active` 가 SSOT 라 단일 홈서버에서 Redis 소실 = 전원 강제 로그아웃(fail-closed). access 는 어차피 15분 무검사라 도난탐지 순이익이 미미했다 | `denyjti:{jti}` · `app/security/jwt.py` |
| 3 | 2026-06-20 | **마이그레이션은 forward-only · expand→contract** | `deploy.sh` 롤백은 **컨테이너 이미지만** 되돌린다. 파괴적 변경이 배포와 같은 리비전에 섞이면 롤백된 구 이미지가 새 스키마에서 즉시 크래시한다 | `backend/alembic/` |
| 4 | 2026-07-12 | **홈 = 해외 사진 피드 → 국내 매칭** | 업로드 검색은 "좋은 사진을 먼저 가져와야 하는" 콜드스타트 마찰이 본질이고, 큐레이션은 운영 손이 상시 들어간다. 투자처를 콘텐츠가 아니라 매칭 엔진으로 옮긴다 | `GET /explore` · `GET /overseas/{id}/matches` |
| 5 | 2026-07-16 | **KTO 이미지 경계는 공공누리 `cpyrhtDivCd`** | 구 "다운로드·재호스팅 금지" 는 오독이었다 — 실체는 콘텐츠랩 **파일데이터**를 소스로 쓰면 OpenAPI 활용 불인정이라는 규정으로 이미지와 무관(2026-07-16 운영사무국 확인 + 설명회·OT·매뉴얼 원문 재분석) | `workers/img-proxy/` · `app/kto/display.py` |
| 6 | 2026-07-17 | **디자인 SSOT = 구현된 앱** | 목업이 리포에 쌓이면 "어느 쪽이 기준인가" 로 SSOT 가 이중 정의된다. 신규 화면은 일회성 html 핸드오프로 만들고 구현 후 폐기 | `mobile/src` |
| 7 | 2026-07-17 | **KTO 재시도는 transient-only** (429·5xx·타임아웃·네트워크) | 비일시 4xx(잘못된 serviceKey·파라미터)까지 3회 재시도하면 성공 가능성 0인 호출로 일일 쿼터(실측 ~1,000콜)를 태운다 | `app/kto/client.py` |
| 8 | 2026-08-10 | **상세 프리워밍은 `detailCommon2` 1콜만** | 모수가 5만이 아니라 attraction 11,575곳이었다. `detailIntro2` 까지 2콜로 늘리면 29일이 걸리는데 얻는 게 빈약하다 — `usetime` 56% 가 "상시 개방", `parking` 91% 가 한 단어, `usefee` 유효율 0.9% | `scripts/prewarm_details.py` |
| 9 | 2026-08-11 | **여행 탭은 채팅-first, 검색은 결정적·작문만 LLM** | 아래 상세 | `POST /agent/chat` · `agent/services/` |
| 10 | 2026-08-19 | **문서는 5개 · ADR 은 이 표로 접는다** | 아래 상세 | `docs/` |
| 11 | 2026-08-19 | **KTO 상세 3콜은 독립 정산 · 프리워밍은 라이브 몫을 남긴다** | `detailCommon2` 일일 쿼터는 실측 ~600콜인데 프리워밍이 04:37 KST 에 전부 태웠다(written=599·kto_failed=200). 게다가 `gather` 가 그 429 하나로 성공한 `detailImage2`·`detailIntro2` 까지 버려 상세 화면이 통째로 비었다 | `app/modules/spots/services/detail.py` · `prewarm_job.py` |
| 12 | 2026-08-19 | **대화 이력은 참고 자료 — 넘치면 잘라 쓰고 턴을 거절하지 않는다** | 20장을 돌려준 턴이 다음 턴의 `spotIds`(상한 8)를 넘겨 `VALIDATION_FAILED` 로 죽었고, 재시도는 같은 시드를 재생해 영구 실패했다. 구 `v*` 빌드는 OTA 를 못 받으므로 관용은 서버 쪽에 있어야 한다 | `app/modules/agent/schemas.py` · `travel/stores/chat-store.ts` |

## 상세

### 9. 여행 탭 — 검색은 결정적, 작문만 LLM 스트리밍

여행 탭은 2026-07-25 부터 2026-08-11 까지 마법사 → 대화형 에이전트 → 조건 시트
폐기 → 지도 위 캐러셀 → 상승 패널 → 채팅 트랜스크립트로 여섯 번 갈아엎었다.
지금 서 있는 자리만 적는다.

**검색은 결정적으로 유지하고, 작문만 LLM 스트리밍에 맡긴다.**

- 흐름: 의도 추출(LLM) → **결정적 SQL/pgvector 조회** → 네이버 블로그 그라운딩
  (≤4콜, 실패 무해) → 라이터가 산문을 스트리밍.
- 라이터는 도구 결과에 있는 사실만 쓴다. 장소는 서버가 검증한 카드로만 노출한다.
- 진입점은 `POST /agent/chat` (SSE). **SSE 응답은 JSend 봉투의 유일한 예외**다 —
  스트림 시작 전 오류만 봉투로 나가고, 이후는 `event:` 프레임이다.
- LLM 공급자는 `LLM_PROVIDER` 로 고른다(`gemini` 기본 · `deepseek` · 로컬 `codex`).
  Gemini 429 는 여행 탭이 실제로 맞는 한계라 대체 경로를 열어 뒀다.

**왜 검색을 LLM 에 안 맡기나** — 관광지 이름을 LLM 이 지어내면 상세(`/spots/{id}`)와
저장이 둘 다 404 다. 존재하지 않는 장소를 그럴듯하게 말하는 것이 이 제품에서
가장 비싼 실패다.

**왜 SSE 인가** — 라이터 스트림 자체가 수 초라 단일 JSON 이면 빈 화면이 길어진다.
2026-07-25 에 "체감 3초 초과 시 재검토" 조건을 달아 뒀고, 실측이 그 선을 넘었다.

**폐기된 갈래** (되살리려면 근거부터 다시 재야 한다):
`/travel-map` 전용 지도 화면 · `GlassSheet` peek/half/full · 지도 위 고정 3층
캐러셀 · 상승 패널 · 문맥 칩 상태 기계 · 카드 한 번 탭 = 앵커 · 턴마다 붙던
`tagBasis` 각주.

### 10. 문서는 5개, ADR 은 표로 접는다

**Diátaxis 4분류(`explanation`·`how-to`·`reference`·`adr`) 를 접고 `README` +
`CLAUDE.md` + `architecture` + `api` + `decisions` 5개로 간다.**

- 문서 53개 중 ADR 20편의 12편이 3주 사이 여행 탭 재설계 연쇄였고, 서로를 대체하며
  현행을 설명하는 건 마지막 하나뿐이었다. 신규 참여자가 `0011 칩 상태 기계` 를
  읽으면 **지금 존재하지 않는 UI** 를 배운다.
- ADR 불변성이 지키려던 건 "결정 기록이 사후 조작되지 않는 것"이고 그건 git 이
  이미 보장한다. 파일을 지워도 `git log --diff-filter=D` 로 전문이 나온다.
- `how-to/` 7편은 대부분 `CLAUDE.md` 의 Commands 절과 중복이었고,
  `reference/travel-tab.md`·`profile-tab.md` 는 **화면 SSOT = 구현된 앱**(결정 6)과
  정면으로 중복되며 이미 드리프트 중이었다.
- `docs/superpowers/` 는 세션 스크래치라 `.gitignore` 로 보낸다 —
  `.superpowers/` 는 이미 그렇게 하고 있었다.

**대가**: 문서 하나가 길어진다(`architecture` 약 340줄). 목적별로 쪼개는 대신
문서 안 목차로 찾게 한다 — 파일이 53개일 때보다 찾기 쉽다는 판단이다.
