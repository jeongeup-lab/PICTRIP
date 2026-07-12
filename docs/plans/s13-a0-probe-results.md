# S13 A0 프로브 결과 — Wikidata SPARQL · Commons 메타데이터 · 핫링크 정책

조사 일시: 2026-07-12 (KST) · 브랜치 `feat/s13-a-data-foundation`
대상 스펙: S13 §10.2(데이터 소스) · §10.5(이미지 핫링크). 이 문서는 Task A2(SPARQL
페치)·A3(Commons 메타데이터·핫링크 URL)의 쿼리 전략·필드 경로 SSOT다.

공통 User-Agent: `PicTripDataBot/1.0 (https://pictrip.org; dev@pictrip.org)`

---

## Step 1 — SPARQL 프로브 (일본 Q17, P31/P279* UNION 3클래스)

쿼리: `wdt:P17 wd:Q17`(일본) + `P18`(이미지 필수) + `sitelinks >= 10` + `ko` 라벨
필수, 클래스 `Q570116`(관광지)·`Q33506`(박물관)·`Q16560`(궁전)을 UNION,
`schema:description`(ko)는 OPTIONAL. `LIMIT 500`.

측정값:

| 항목 | 값 |
|---|---|
| HTTP 상태 | 200 |
| 응답 시간(curl total) | **5.8s** (WDQS 60s 제한 대비 여유) |
| 반환 행 수 | 101 (LIMIT 500 미도달 = 조건 만족 항목 전량) |
| `desc`(ko) 보유 행 | 34 / 101 |
| **한국어 설명 커버리지** | **0.337** |

샘플 행:

```
Q798766  고베 포트 타워   desc="일본의 효고현 고베시 주오구에 있는 타워"  links=23
Q1201304 교토 타워        desc=(없음)                                    links=21
Q843426  코스모 클락 21   desc=(없음)                                    links=12
```

관찰:
- **타임아웃 없음.** UNION 3클래스를 한 번에 실행해도 일본 기준 5.8s. 클래스별 분할 불필요.
- `wdt:P18` 값은 이미 `http://commons.wikimedia.org/wiki/Special:FilePath/<파일명>`
  형태로 반환된다. Step 3의 핫링크 URL을 그대로 재사용 가능(파일명 별도 파싱 불필요).
- 커버리지 0.337 < 0.5 → 아래 백로그 참조.

### 백로그 (이번 범위 아님)
한국어 설명 커버리지가 0.337로 0.5 미만. 스펙 §10.2의 **위키백과 요약 보강**을 백로그로
기록한다. 스키마는 `description_ko`를 nullable로 두어 결측을 흡수하고, 후속으로 한국어
위키백과 REST summary API로 채우는 태스크를 별도 편성.

---

## Step 2 — Commons `extmetadata` 배치 API

엔드포인트: `commons.wikimedia.org/w/api.php` · `action=query&prop=imageinfo&iiprop=extmetadata`

단일 파일(`File:Tokyo Tower 2023.jpg`) HTTP 200. 필드 경로 확인 결과:

| A3가 쓸 필드 | 경로 | 예시 값 |
|---|---|---|
| 저작자 | `imageinfo[0].extmetadata.Artist.value` | `<a href="//commons.wikimedia.org/...">...` (HTML 포함) |
| 라이선스 약칭 | `imageinfo[0].extmetadata.LicenseShortName.value` | `CC BY-SA 4.0` |
| 라이선스 URL | `imageinfo[0].extmetadata.LicenseUrl.value` | `https://creativecommons.org/licenses/by-sa/4.0` |
| (보조) 라이선스 코드 | `...extmetadata.License.value` | `cc-by-sa-4.0` |
| (보조) 출처 | `...extmetadata.Credit.value` | `<span ...>Own work</span>` |
| (보조) 표기 필요 | `...extmetadata.AttributionRequired.value` | `true` |

- `Artist.value`·`Credit.value`는 **HTML을 포함**하므로 A3에서 태그 제거/링크 추출 필요.
- 퍼블릭 도메인 파일은 `LicenseUrl`이 없을 수 있음(아래 배치의 CosmoClock21 =
  `LicenseShortName: Public domain`). 필드는 nullable 취급.

**50개 배치 확인**: `titles=A|B|C`(파이프 URL 인코딩 `%7C`)로 임의 3개 파일 요청 →
`query.pages`에 **3개 페이지** 모두 반환, 각기 독립된 `extmetadata` 보유:

```
File:CosmoClock21 2006-05-21.JPG        Lic: Public domain
File:Kobe port tower12s3200.jpg         Lic: CC BY 2.5
File:Kyoto Tower 2023-12 ac (1).jpg     Lic: CC BY-SA 4.0
```

배치 정상 동작. `titles`는 최대 50개 파이프 결합으로 호출(MediaWiki API 한도 = 비봇 50).

---

## Step 3 — 핫링크 (Special:FilePath 리다이렉트 + UA 정책)

리다이렉트 체인 (기본/브라우저 UA):

```
GET commons.wikimedia.org/wiki/Special:FilePath/Tokyo%20Tower%202023.jpg?width=800
 302 → commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Tokyo_Tower_2023.jpg&width=800
 301 → upload.wikimedia.org/wikipedia/commons/thumb/5/58/Tokyo_Tower_2023.jpg/960px-Tokyo_Tower_2023.jpg
 200  content-type: image/jpeg
```

- 최종 URL 형태: `upload.wikimedia.org/wikipedia/commons/thumb/<h1>/<h2>/<파일명>/<W>px-<파일명>`
- `?width=800`은 **가장 가까운 표준 버킷으로 올림** → 최종 `960px`. 임의 폭을
  직접 조립하면 400 발생(직접 `.../800px-...` 요청 = HTTP 400 확인). **A3는 폭을
  직접 조립하지 말고 `Special:FilePath/<name>?width=N` 형태로 핫링크할 것.**

### ⚠️ UA 차단 (다운스트림 필수 조치)

Wikimedia가 라이브러리 기본 UA를 차단하기 시작함(phabricator **T400119**). 최종
upload.wikimedia.org URL에 대한 UA별 결과:

| User-Agent | 결과 |
|---|---|
| `okhttp/4.9` / `okhttp/4.9.0` / `okhttp/3.12.1` / `okhttp/5.0.0-alpha.11` | **403** |
| `okhttp` (버전 없음) | 200 |
| 빈 UA (`""`) | 403 |
| `Dalvik/2.1.0 (... Android 13; Pixel 7 ...)` | 200 |
| `Mozilla/5.0 (iPhone; ... iPhone OS 17_0 ...)` | 200 |
| `CFNetwork/1490.0.4 Darwin/23.1.0` | 200 |
| `PicTrip/1.0` (커스텀) | 200 |

403 응답 본문:
```
Please set a user-agent and respect our robot policy https://w.wiki/4wJS.
See also https://phabricator.wikimedia.org/T400119.
```

차단 패턴은 **정확히 `okhttp/<버전>` 문자열**(및 빈 UA). iOS(CFNetwork/NSURLSession)와
Dalvik, 커스텀 UA는 통과. FilePath 진입점도 okhttp UA면 동일하게 403(체인 미진입).

**모바일 함의(C 태스크로 전달):** Android RN `<Image>`는 Fresco→okhttp를 쓰며 기본
UA가 `okhttp/x.y.z`라 **그대로면 403으로 이미지가 안 뜬다.** 이미지 요청에 커스텀
`User-Agent` 헤더를 반드시 붙여야 함:
`source={{ uri, headers: { 'User-Agent': 'PicTrip/1.0 (https://pictrip.org)' } }}`.
iOS는 기본 UA로도 200이지만 일관성을 위해 양 플랫폼 모두 헤더 설정 권장.

---

## 결정

- **A2 쿼리 전략: UNION 유지** — 일본 UNION 3클래스가 5.8s/HTTP 200으로 60s 제한 내
  완료. 클래스별 분할 불필요. (국가별로 항목 수가 큰 곳에서 60s에 근접하면 그때
  해당 국가만 분할 — 현시점 기본은 단일 UNION 쿼리.)
- **A3 필드 경로 확정**: `extmetadata.Artist.value`(HTML) · `LicenseShortName.value` ·
  `LicenseUrl.value`(PD면 결측 가능). 50개 `titles` 파이프 배치 정상.
- **A3 핫링크 URL 확정**: `Special:FilePath/<name>?width=800` 사용(폭 직접 조립 금지).
- **모바일(C) 필수 조치**: Commons 이미지 요청에 커스텀 `User-Agent` 헤더 부착
  (okhttp 기본 UA는 403 — T400119).
- **백로그**: 한국어 설명 커버리지 0.337 → 위키백과 요약 보강 태스크 별도 편성,
  `description_ko` nullable.

---

## A8 부트스트랩 결과 (2026-07-12)

### Step 1 — ETL 본실행 (CT111)

- `sync_runs` id=49: mode=overseas **success**, 103 API 콜, 25분(1,526s).
- 적재 **2,347행**(fetched 2,378, updated 31) — 목표 2,000~5,000 충족,
  `MIN_SITELINKS` 조정 불필요. 35개국, 상위: US 271 · IT 248 · JP 219 · CN 188.
- 커버리지: image_url 100% · image_author **96%**(null 4% — Commons
  normalized-title 에지, 허용 수준) · description_ko **26%**(A0 예측 0.337보다
  낮음 — 위키백과 요약 보강 백로그 유지).

### Step 2 — 샘플 100 검수

- 불량 ~4% → `_CLASS_QIDS` 재조정 불필요.
- 불량 패턴 2종: ① 침몰 군함/난파선(전쟁 무덤·비방문지), ② 논쟁적 기념물.
  경계선: 코무네(지자체) 항목 — 유명 관광도시(시라쿠사·아그리젠토·메시나·타란토)는
  유지, 무명 코무네만 숨김.
- 전수 패턴 스캔 후 **10건 `is_hidden=true`** (SQL 직접 — 임베딩·match 캐시 생성
  전이라 캐시 무효화 불요): 난파선 6(Q1060785 HMS 햄프셔 · Q641685 SMS 폰데르탄 ·
  Q698398 SMS 힌덴부르크 · Q686392 AHS 센타우로 · Q155222 샤른호르스트 ·
  Q2616711 안티키테라 난파선), 무명 코무네 3(Q39971 젤라 · Q34615 아드리아 ·
  Q72356 포조마리노), 논쟁 기념물 1(Q4343512 Iğdır).
- 박물관함(USS 요크타운·뉴저지·미주리·렉싱턴, HMS 벨파스트·빅토리)은 실관광지로 유지.
- 텍스트 품질: 일부 위키데이터 ko 설명이 비문(예: Q10288 오사카성 공원) — 소스
  verbatim 원칙 유지, 보강은 백로그.

### Step 3 — 임베딩 배치 (CT112)

- 1차 실행: Commons 429 레이트리밋으로 76/2,347만 성공(무스로틀 동시 8).
  90s 쿨다운 후 `--concurrency 1` 프로브도 19/50에서 재차 429 → 코드 수정 필요 판정.
- PR #116: Retry-After 존중 지수 백오프(최대 6회·120s 캡) + 슬롯당 0.3s 페이싱,
  기본 동시성 8→2. 머지·배포 후 재실행 → **2,252/2,252 성공, 실패 0**(46분).
  `embedding IS NULL` = 0.

### Step 4 — 매칭 임계값 튜닝

- 무작위 300 스팟 rank별 거리 분포: rank-1 p50 0.233 / p90 0.310 / p99 0.393,
  rank-3 p50 0.253 / p90 0.328 / p99 0.426.
- **스펙 후보 0.40/0.45/0.50은 전부 무의미** — top-3 거리의 p99조차 0.43이라
  아무것도 거르지 못함. 실거리는 0.12~0.35에 몰려 있음.
- 유명 25 + 무작위 10 눈검사: 좋은 매칭(선돌↔스톤헨지·오벨리스크, 전탑↔대안탑,
  독일마을↔프라이부르크, 이슬람거리↔아야 소피아, 산↔후지·몽블랑·베수비오)은
  0.31 이하에 몰림. 관측 잡음(백악관→소금집델리 0.338·보원흑삼 0.330,
  루브르 0.34~0.35, 콜로세움 0.34)은 0.33부터 시작.
- **확정: `MATCH_DISTANCE_MAX = 0.32`** (config 기본값 커밋, .env 오버라이드 없음).
  0.32 이하에도 무명 스팟 일부 잡음(쉴트호른→식당 0.270)은 잔존 — CLIP 시각
  유사도의 한계로 수용, 더 조이면 상기 양질 매칭이 잘림. 매칭 3개 미만/0개
  노출은 스펙상 허용(정직-미니멀).
