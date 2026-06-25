# S11 — 외부 벤치마크 & 심층분석 개선노트

> 세션 S11(2026-06-21, 로드맵 외 보강 패스). 입력: S1~S10 전 스펙 + 관리자 콘솔 + 목업 +
> 현 백엔드 코드(ground truth) + **6개 병렬 MCP 리서치**(Exa 웹검색/페치, context7, GitHub
> 코드검색). 목적: "다른 팀들은 어떻게 하는가"를 근거로 잠긴 설계를 검증하고, **추가형
> 보강**과 **재고가 필요한 결정**을 분리해 제시한다.
>
> **S11은 S1~S10의 잠긴 결정을 덮어쓰지 않는다.** §1~§6은 잠긴 결정을 *강화*하는 추가형
> 노트(구현 세션이 그대로 흡수)이고, §7은 **잠긴 결정을 뒤집어야 하는 항목 → 사용자 승인
> 필요**다. 결정이 바뀌면 해당 S 문서에 반영하고 `session-context` 결정 로그를 갱신한다.

## 0. 총평 & 우선순위

전 설계를 외부 best-practice와 대조한 결론: **기술 결정의 대부분이 베스트프랙티스에
부합하거나 그 이상**이다(아래 "검증됨" 목록). 보강할 가치가 있는 것은 소수이고, **진짜
재고가 필요한 건 공모전 전략 1건**이다.

**검증됨(변경 불필요 — 외부 근거로 확인):**
- `halfvec(512)` CLIP 저장: float32 대비 recall <1% 손실·저장 ~50% 절감 → **정답**.
- `show_flag` soft-delete + 부분 인덱스, URL-only 이미지(cpyrhtDivCd Type3), 7일 overview
  캐시, 신규 `lcls_systm` 택소노미: **공개 레퍼런스 구현 다수보다 오히려 엄격/정확**.
- 인증 denylist 모델 + fail-open(단일 Redis): Halodoc·DEV 등 동일 선택 **선례 존재, MVP에
  타당**. 회전 미채택은 refresh-race 버그 클래스를 통째로 회피하는 **숨은 이점**까지 있음.
- 딥링크 토폴로지(associated domains + autoVerify + CDN 연결파일 + 스킴 폴백): Expo SDK 56
  **현행 권장과 정확히 일치**. deferred DL 포기도 무네이티브 제약상 옳은 트레이드오프.
- 서버주도 홈피드(슬롯 고정·콘텐츠 서버선택)·polymorphic `curations` 단일테이블: 규모상 **타당**.

**우선순위 보강(추가형, §1~§6):**
1. **[전략·최우선] 데이터 융복합 갭** — 공모전 채점축 "데이터 활용 적절성(20)"·"융복합"에서
   PicTrip는 **단일 소스(TourAPI)** 라 가장 얇다. 이미 적재된 `spot_concentration`(집중률
   예측)을 *화면 추가 없이* 카드/상세 혼잡도 배지로 재융합 → 최저비용 최고레버리지. → **§7-A(승인 필요)**.
2. **[기술] 사진검색 정확도** — 고정 임계 0.60은 ViT-B/32 image-image엔 과하게 빡빡할 소지;
   `round(cos×100)` % 게이지는 사용자에게 "60%=훌륭한 매치"로 **오해 유발**. + 임베딩 36%
   공백의 **조용한 실종** 미대응. → §2.
3. **[기술] auth 보강** — 30일 *고정* refresh는 활동 유저도 정확히 30일에 강제 로그아웃 →
   **슬라이딩**으로. + 공급자별 id_token 검증 규약(Apple base64url nonce, Google 다중 aud,
   provider+sub 키) 명문화 + SecureStore 접근성 + single-flight. → §3.
4. **[기술] 딥링크 함정** — assetlinks **지문 2개**(Play 앱서명 + EAS 업로드), AASA `components`
   문법, **웹 폴백 페이지 + Smart App Banner**, CF 리다이렉트로 딥링크 경로 가리지 말 것. → §4.
5. **[기술] 피드 견고화** — type↔region_cd/mood_id **CHECK 제약**, KST자정 일괄만료 **지터**+
   on-publish 무효화, (랜덤채움→품질게이트 랭킹은 §7-B 승인 필요). → §5.
6. **[정합] 문서 갭** — nearby 세분라벨(기존 인지)·동의버전 수명주기·아바타 URL 404 폴백 등. → §6.
7. **[운영] 관리자 콘솔(A1)** — A1~A8 설계 대부분 정설 부합. 인증 게이트(공개 노출 Basic →
   **CF Access를 Phase 1 필수로 승격**)·트리거 audit 1줄, 2건만 보강. SQLAdmin 미채택은 정당
   (모니터링≠CRUD). → §9.

---

## 1. 공모전 전략 (가장 결정적)

> 근거: 2026 공모문 채점 루브릭(Exa로 KTO PDF 미러 확보) + 역대 수상작 + 현 코드 자산.

**확인된 1차 채점(100점, crosscheck=공식 공고문 PDF):** 서비스 기획력(구체성·독창성·트렌드)
**30** · 완성도(기능·안정·편의) **30** · **데이터 활용 적절성 20**(*공사 OpenAPI 활용 필수=각주)
· 발전성 **20**. 최종 PT(top5)=적정성30/완성도30/실용성25/발표15. **게이팅**: 심사 대상은
*"공사 OpenAPI 필수 활용 + 개발 완료(스토어/라이브) 완성 서비스"* — 프로토타입 불가. **+2점
가점 2종**: ❷ 지역특화(전국 아닌 1개 지역, 서울 제외) · ❶ 신보 Start-up NEST 선정기업.

> ✅ **마감일 = 2026-09-21 16:00 KST 확정**(사용자 확인 2026-06-21). 리서치가 찾은 "접수
> 2026-05-06·1차심사 10월"은 다른 회차/공모전이라 무시. `CLAUDE.md` 1차 deadline 정확. 남은
> 기간 ≈ 3개월 → 구현은 S10 Stage A(백엔드)부터, §7-A 재융합은 자산 재사용이라 저비용 우선착수 가능.

| 발견 | 함의 | 권고 |
|---|---|---|
| **컨셉 선례 존재**(crosscheck로 톤다운): GitHub `1223v/Photoplace`가 *자칭* "2022 관광데이터 공모전 수상작"(AI 추천 여행지, TourAPI v4+Kakao). **단 공식 KTO 대상/최우수 명단엔 없음**(우수/장려 추정, 연도 2021~2022 모호, "사진 업로드→매칭" UX는 README 미명시=추론). ViT/CLIP 사진추천 한국 선례 4+개(Isanghada·thisis05·JuhyeonJung·koCLIP ASK2025). | 유사 컨셉 다수 존재 → 컨셉 *독창성*만으론 차별 약함(상위 수상작 단정 금지). | **규모(68k·실 pgvector HNSW halfvec)+ 출시 완성도**로 차별. PT에 koCLIP cold-start 학술 프레이밍 인용(데이터 활용성·독창성 훅). |
| **단일 데이터소스**: 대부분 최우수상은 TourAPI+α(날씨·항공·카카오·방문자 빅데이터) 융복합. PicTrip는 TourAPI 단일. | "데이터 활용 적절성(20)"·"융복합"에서 **가장 얇음**. | **§7-A**: 폐기한 `spot_concentration`(집중률 예측, **이미 6,387행 적재·`sync_concentration.py` 생존**)을 *화면 추가 없이* 카드/상세 "지금 한산/붐빔" 배지로 재융합. TourAPI 계열이라 "공사 OpenAPI 필수" 게이트도 충족. |
| **지역특화 +2점 가점·RTO 특별상** 다수 수상작 활용. PicTrip=전국 generalist. | 가점 포기. | 전국-스케일 데이터 깊이로 상쇄(의도된 트레이드오프). 데모 시 1개 지역 심화 스토리 보강 검토(선택). |
| **라이브/출시 게이트** | TestFlight 파이프라인 보유. | 심사 전 **스토어 가용성 확정** 체크리스트화. |

**핵심:** 기획/완성도(무거운 축)는 PicTrip 강점. **데이터 활용성(20)이 유일한 약점**이고,
그 해법(`spot_concentration` 재융합)은 *이미 만들어둔 자산 재사용*이라 비용 최저다.
출처: 공모문(scribd 1026171433 · touraz.kr) · github 1223v/Photoplace · data.go.kr 15128555(집중률)·15101972(방문자) · ASK2025 koCLIP.

---

## 2. 사진검색 / CLIP / pgvector (S4·S7·S9)

### 2.1 임계값 0.60 — 재튜닝 필요(고정 하드컷은 위험) [추가형]
- **근거**: ViT-B/32 image-image 코사인은 무관쌍이 ~0.2–0.4 좁은 밴드, 유관쌍 ~0.6–0.8에
  몰림. 0.60 하드컷은 "닮은 풍경"의 상당수(0.55–0.75)를 **빈 결과로 떨굴 소지**. dedup용
  임계(0.85+)와 혼동 금지. 보편 지침: **자기 코퍼스에서 히스토그램으로 FP/FN 교차점 캘리브레이션**.
- **권고**: S4의 "구현 시 ~0.60 튜닝" 헷지를 **실행**한다 — 라벨드 쿼리/스팟 쌍 ~100–200개로
  히스토그램 → 임계 확정(0.50–0.70 예상). **하드컷보다 top-N + 소프트 플로어**(항상 best K
  노출, 플로어 미만은 dim) 권장 — CLIP 좁은 밴드에 더 견고. 출처: theneuralbase.com/clip,
  ternaus/clip2classdist, arxiv 2411.05195(MMVP).

### 2.2 유사도 % 표시 — 리매핑 필요 [추가형·UX]
- **근거**: `round(cos×100)`을 그대로 "유사도%"로 보이면(S9 §1.4), 훌륭한 매치도 60~75%로,
  90%+는 사실상 안 뜬다 → 사용자에겐 **불안하게 낮게** 읽힘(CLIP의 의미적 편향까지 겹침).
- **권고**: 표시값을 **버킷 라벨**("매우 닮음/닮음")로 바꾸거나 기대 매치밴드를 0–100으로
  스트레치. 원시 코사인×100 노출 금지. (디자인 오너 확인 항목.)

### 2.3 HNSW JOIN 함정 — 구체적 쿼리형 명문화 [추가형·S7 §10 강화]
- **근거**: S7 §10이 정확히 지적함(JOIN/CTE 안에선 HNSW 미사용 → seqscan+sort ~175ms).
  실제 pgvector의 확정된 동작(issues #275/#609/#703).
- **권고**: PicTrip 사진검색은 쿼리벡터가 *업로드 이미지의 즉석 임베딩(바인드 파라미터)* 이라
  `ORDER BY embedding <=> $1::halfvec(512) LIMIT 30`이 **자연히 인덱스 친화형**. S9/S10에서
  "**ANN ORDER BY + LIMIT을 임베딩 베이스 테이블에 직접, 그 결과 id로만 메타 조인**" 패턴을
  강제하고 cross-join 거리식 금지. `EXPLAIN`에 `Index Scan using <hnsw>` 확인을 검증 게이트에.
  (스팟↔스팟 유사도가 필요해지면 스칼라 서브쿼리형: `... <=> (SELECT embedding FROM spots WHERE content_id=$1)`.)
  출처: crunchydata HNSW, dbi-services pgvector guide, pgvector #609.

### 2.4 임베딩 36% 공백 — 조용한 실종 대응 [추가형]
- **근거**: 임베딩 없는 스팟은 ANN에 **영원히 안 뜸**(카탈로그 1/3 암흑). S4 빈상태가 이를
  가림 — 좋은 스팟 5개 옆에서도 "못 찾음"이 나올 수 있음.
- **권고**: (1) **임베딩 백필 ~100%를 사진검색 릴리스 게이트로**(임계 튜닝보다 큰 레버).
  (2) GPS 있을 때 결과 thin/공백이면 메타기반(거리+카테고리) **graceful degradation** 보조레일.
  (3) 커버리지%·빈결과율 **모니터링**. 한국 선례도 카페/식당은 NL/카테고리 폴백으로 보완.
  출처: aiopsschool hybrid-search F1, Azure HorizonDB backfill, github thisis05/Isanghada.

### 2.5 pgvector 0.8 iterative scan — 필터 시에만 [추가형·검증항목]
- 사진검색에 `WHERE category/region` 필터를 붙이면 0.8 이전은 ef_search 후필터로 **과소결과**.
  필터 추가 시 `hnsw.iterative_scan = relaxed_order`. **프로덕션 pgvector ≥0.8 확인** 필요(미만이면
  부분인덱스+필터가 조용히 적은 결과 반환). 출처: AWS pgvector 0.8 blog, pgvector README.

---

## 3. 인증 / OIDC (S1·S8·S9)

전제: denylist 모델·fail-open·in-memory/SecureStore 분리·access 15분 무검사 = **MVP에 타당,
선례 있음**. 아래는 보강.

### 3.1 30일 refresh를 슬라이딩으로 [추가형 — 가장 실질적 UX 보강]
- **근거**: *고정* 30일+무회전+무슬라이딩이면 어제 켠 활동 유저도 가입 30일째 **강제
  로그아웃**. 소비자앱 표준은 슬라이딩 idle + 절대 상한(예 access 15m/refresh 30d 슬라이딩/
  절대 90d). OWASP ASVS도 절대만료를 *요구*하고 슬라이딩은 UX 권장.
- **권고**: refresh 성공 시 **같은 무회전 모델로 exp만 재발급**(jti/claims 동일, exp만 갱신)
  → 활동 유저 무중단, 30일 미사용자만 재로그인. ⚠️ S8/S9의 "입력 토큰 그대로 에코"와 **충돌**
  → S8 §2.2 / S9 §3.2 문구 보정 필요(에코 대신 exp-슬라이딩 재민트). 출처: CIAM Compass,
  toolbox365 토큰수명, OWASP ASVS V10.4.8.

### 3.2 공급자별 id_token 검증 규약 명문화 [추가형 — 보안 필수]
- **Apple**: `iss=https://appleid.apple.com`, `aud=네이티브 bundleID`, **ES256**, `nonce`는
  **SHA-256(raw) base64url(무패딩)** — hex 비교는 영원히 불일치(Supabase #2378 실제 버그).
  이름은 최초 1회만, 식별은 `sub`.
- **Google**: `aud`는 **플랫폼별 client_id 집합**을 허용(Android/iOS/Web 별도). 식별 `sub`.
- **Kakao OIDC**: 콘솔에서 OIDC 활성+scope `openid` 없으면 id_token 미발급. `iss=https://kauth.kakao.com`,
  JWKS `/.well-known/jwks.json`, nonce 검증.
- **공통**: 서명·iss·aud·exp·nonce 전부 검증, `alg:none` 거부, **유저 키 = provider+sub
  (이메일 금지 — 재할당/변경됨)**. 출처: Apple verifying-a-user, supabase auth #2378, Google backend-auth, kakao oidc.

### 3.3 운영·클라 디테일 [추가형]
- **Redis 도달성 알림**: fail-open이 *조용한* 폐기갭이 되지 않게 헬스체크/알림. 탈퇴 시 Redis
  다운 노출창(최대 다운지속+15분 access)을 문서에 명시.
- **SecureStore**: refresh에 `WHEN_UNLOCKED_THIS_DEVICE_ONLY`(iCloud 키체인 로밍 차단). ⚠️
  iOS는 **앱 삭제 후에도 키체인 잔존** → 설치 후 최초 실행 시 정리/방어.
- **single-flight refresh**: 동시 401 한 번만 refresh 공유(무회전이라도 thundering herd 방지).
출처: oneuptime RN JWT, expo SecureStore 문서, michal-drozd jwt-revocation.

---

## 4. 딥링크 (S8·S9·S10)

토폴로지 = **현행 권장과 일치**. 아래는 실패율 높은 디테일.

### 4.1 assetlinks 지문 2개 — 최대 프로덕션 버그 리스크 [추가형 — 체크리스트화]
- **근거**: EAS+Play 앱서명이면 키가 둘(EAS 업로드키 ≠ Play 재서명키). 스토어 설치 유저는
  **Play 앱서명 지문**으로 검증 → 하나만 넣으면 "디버그OK·운영깨짐". 증상: `pm get-app-links`가
  `legacy_failure`, 선택창 노출.
- **권고**: `sha256_cert_fingerprints`에 **둘 다**(Play Console→앱 서명 SHA-256 + `eas
  credentials -p android` 업로드키 SHA-256). S10 CF Pages 작업의 명시 체크라인으로. 출처: expo android-app-links.

### 4.2 AASA `components` 문법 + CF 무리다이렉트 [추가형]
- iOS 17+는 `paths`보다 `components` 선호. `*`는 `/`·`.` 미매치(`/spots/*`는 단일세그먼트만 —
  contentId/slug 단일세그먼트라 OK). **AASA는 설치/스토어업데이트 때만 fetch** → `/spots/*`·
  `/curations/*` **둘 다 최초 빌드에 포함**(나중 추가하면 기존유저 미인식).
- ⚠️ **CF Pages `_redirects`/Always-Use-HTTPS/마케팅 리다이렉트가 딥링크 경로를 건드리면
  유니버설 링크가 조용히 깨짐**(iOS 18 회귀 다수). `curl -I`로 `/.well-known/AASA` 200·JSON·
  no `location:` 확인을 검증 게이트에. 출처: apple TN3155, developer.apple.com/forums/thread/780496.

### 4.3 웹 폴백 페이지 + Smart App Banner [추가형 — deferred 손실의 최저비용 완화]
- **근거**: deferred DL 포기는 옳음. 단 "무네이티브→불가능"은 약간 과함 — `expo-clipboard`
  (1st-party) 기반 클립보드 패스는 *가능*하나 iOS16+ 붙여넣기 권한 프롬프트로 UX 나빠 **의도적
  유보**가 맞다. 진짜 완화책은 따로 있음.
- **권고**: 미설치 유저가 여는 `pictrip.org/spots/{id}` **웹 페이지에서 스팟을 실제 렌더 +
  Apple Smart App Banner(`<meta name="apple-itunes-app">`) + Play 설치 버튼**. 이미 도메인
  보유라 무료. S8 §3 리다이렉트 Function 대신/추가로 "리치 폴백 페이지"로 격상 검토. 출처: shipnative deep-linking, apple smart-app-banner.

### 4.4 스킴 `pictrip://` 유지 [검증됨]
- 유니버설 링크와 중복 아님 — dev 툴링·Kakao OAuth 콜백·Expo Go·in-app WebView 폴백에 필요. **유지 정답**.

---

## 5. 서버주도 피드 / 큐레이션 (S2·S7·S8)

### 5.1 type↔스코프 CHECK 제약 [추가형 — 싱글테이블 무결성 회복]
- **근거**: polymorphic 단일테이블은 "region이면 region_cd 필수"를 DB가 못 막음(S7 §3.1이
  "앱 보증, v1 미적용"로 둠). mature 가이드는 이 약점을 **CHECK로 회복** 권장.
- **권고**: `CHECK ((type='region' AND region_cd IS NOT NULL) OR (type='mood' AND mood_id
  IS NOT NULL) OR type='editorial')` 명명 추가(M1). 시드 책임 대신 DB 보증으로 격상(저비용).
  출처: viprasol postgres-inheritance, dolthub polymorphic.

### 5.2 KST자정 일괄만료 → 지터 + on-publish 무효화 [추가형]
- **근거**: 모든 `curation:{id}:spots`가 정확히 00:00 KST에 동시 만료 = thundering herd
  교과서 안티패턴. 결정적 seed라 재빌드는 멱등이지만(심각도↓) 위생은 필요.
- **권고**: (1) 만료에 **지터**(자정±N분 또는 24h±지터). (2) **stale-while-revalidate**(만료 키는
  직전값 서빙+백그라운드 갱신). (3) 에디터 publish/edit 시 **해당 키 즉시 무효화**(편집 반영엔
  자정 대기보다 이게 옳음). (4) 하드 재빌드 시 per-key mutex(`SET NX PX`). 출처: redis thundering-herd, oneuptime redis-expiration.

### 5.3 피드 와이어 형태 — 타입드 블록 배열(선택 보험) [추가형·낮은 우선]
- **근거**: Airbnb GP/Spotify/Yelp/DoorDash는 *순서있는 타입드 섹션 배열*. S2의 "정확히 6+3"을
  응답스키마·파서에 하드코딩하면 향후 개수/순서/4번째 레일 추가가 **깨지는 변경**.
- **권고(선택)**: `[{type:"hero",position,...},{type:"rail",...}]` 순서배열로 내리되 클라는
  당분간 "~6 hero/~3 rail" 기대. 레이아웃 고정은 v1 유지, **와이어만 유연화**. 비용 낮은 보험.
  (강제 아님 — 시간 부족 시 생략 가능.) 출처: airbnb GP, doordash facets.

### 5.4 표지 외부 URL — 조립시 non-null 검증 [추가형]
- 컴플라이언스상 호스팅 불가는 불가피. 단 **피드 조립 시점에 cover의 image URL non-null
  검증 + 폴백 표지(2순위 스팟)**로 깨진 히어로를 안 내보냄. RN은 `expo-image` 디스크캐시라 웹 LCP만큼
  심각친 않으나 broken-image율이 진짜 리스크. 명시적 종횡비로 레이아웃 시프트 방지.

---

## 6. 문서 정합 갭 (내부 교차리뷰 — 저위험 보강)

| 갭 | 위치 | 권고 |
|---|---|---|
| nearby 카드 세분 `lcls_systm3_nm` 라벨이 현 응답에 없음 | S3·S5·S7 §6 이미 인지 | Stage A 직렬화에 추가(이미 계획). **충돌 아님, 추적용 재확인**. |
| 동의버전(`terms_version`) 수명주기: 최초 set 시점·약관 갱신 시 재동의 정책 미확정 | S1·S6·S9 §3.6 | "최초 로그인=가입시점 현행 버전" 명문화 + 약관 갱신 시 재동의 여부 결정(S1 보강). |
| 아바타 URL 404 폴백 미명시 | S6·S9 §3.4 | "URL 404/널 → 모노그램 폴백" 클라 규칙 1줄 추가. |
| `regions-tree` centroid는 컬럼 아닌 런타임 AVG인데 schema-docs에 주석 없음 | schema-docs(미추적) | schema-docs에 "centroid=런타임 AVG, 컬럼 없음" reconcile 노트. |
| `onboarding_seen` 플래그 set 시점(08 push 전/후) 미명시 | S1 | "CTA 탭 시 08 push **전**에 set" 1줄. |
| 0-스팟 레일 처리(랜덤 실패 후 <3) | S2 | "<3이면 레일 생략(밀도 안정)" 규칙 명시. |
| 사진검색 0건 vs 백엔드 현 `PhotoSearchResult` 형 | S4·S9 §4.1 이미 reconcile | 0-length 배열을 에러로 오인 말 것(S10 구현 주의). |

---

## 7. 재고 필요 — 잠긴 결정 뒤집기(사용자 승인 필요)

> 아래 2건은 S1~S10에서 *명시적으로 잠긴/사용자 재결정한* 사항이라 S11이 단독 변경하지 않음.

### §7-A. `spot_concentration` 데이터 재융합 [전략·강력 권고]
- **잠긴 상태**: S7 §5 — "spot_concentration drop_table (2026-06-20 재결정: 보존→폐기)";
  S9 §8.1 — trending 엔드포인트 제거. 단 **테이블·`sync_concentration.py`·trending 서비스는
  코드에 생존**(확인됨, 6,387행).
- **권고**: *트렌딩 화면은 계속 컷*(목업 없음 — UX 프루닝은 옳음). 그러나 **데이터 계층은
  살려서** 스팟 카드/상세에 "지금 한산/보통/붐빔" 혼잡도 배지로 재융합. 공모전 "데이터 활용
  적절성(20)·융복합"의 유일한 약점을 *이미 만든 자산*으로 메움. 신규 화면 0, 신규 테이블 0,
  배지 1개 + 캐시.
- **crosscheck로 강화됨**: 출처 `data.go.kr 15128555 = 한국관광공사_관광지 집중률 방문자 추이
  예측`(KT 이동통신 기반 향후 30일 상대 집중률, 참고문서 `TourAPI_Guide v4.0`)임을 **공식 확정**.
  → **TourAPI 계열이라 "공사 OpenAPI 필수" 게이트를 그대로 충족**하며 데이터 활용 적절성(20)에
  직접 기여. 추가 비용은 배지 직렬화+캐시뿐.
- **트레이드오프**: 무채색 honest-minimal 원칙(혼잡도 배지 없음 — S5 reconcile에서 `crowd`
  제거)과 **상충**. 즉 "디자인 순수성 vs 공모전 데이터점수"의 명시적 선택.
- **결정 필요**: 재융합할까(권고: **예, 카드/상세 배지로**) / 완전 폐기 유지할까.

### §7-B. 랜덤 채움 → 품질게이트 랭킹 [중간 권고]
- **잠긴 상태**: S2 — 손픽 비면 "테마일치 **랜덤**(결정적 seed·일캐시)".
- **권고**: 순수 랜덤은 "제주" 히어로에 thin/무관 스팟이 섞일 수 있음. **품질게이트
  랭킹**(has-image·overview 보유·임베딩 커버리지로 top 버킷 정렬 후, seed는 top 버킷 내
  회전에만)으로 교체 — 결정성·일캐시 유지하며 관련성 하한 보장. NYT 등 에디토리얼은 랜덤 회피.
- **트레이드오프**: 약간의 구현 복잡도↑. 손픽이 차면 어차피 무관 경로(초기 운영에만 영향).
- **결정 필요**: 랜덤 유지 / 품질게이트 랭킹으로 교체(권고: **교체**).

---

## 8. 적용 가이드(승인 후)
- §1~§6 추가형: 해당 S 문서 본문에 흡수 + `session-context` 결정 로그에 "S11" 한 줄.
  (병렬 세션 충돌 위험 → 편집 전 `git status` 재확인, 사용자 요청 시에만 커밋/푸시.)
- §7 승인 항목만: S7/S9(7-A), S2(7-B) 정정 + 결정 로그 갱신. 7-A 승인 시 S8에 혼잡도
  캐시 키 추가, 모바일 카드 컴포넌트에 배지 슬롯.
- 검증 게이트 추가(S10 §4에 합류): EXPLAIN HNSW Index Scan 확인(§2.3), `curl -I` AASA(§4.2),
  `pm get-app-links` verified(§4.1), 임베딩 커버리지% 측정(§2.4).

## 9. 관리자 콘솔 (A1) — 외부 벤치마크

> 입력: `admin/specs/A01-admin-console.md` + 목업 `admin/mockups/`(3p) + 현 백엔드.
> 리서치(2026-06-21 추가 패스): Exa 웹검색×2(내부툴/백오피스 아키텍처 정설, FastAPI SQLAdmin
> vs 분리형 SPA) + GitHub 코드(`bankotij/rbac-admin-platform`·`SenZmaKi/spa-sqladmin`·benavlabs
> FastAPI-boilerplate·`aminalaee/sqladmin`·`jowilf/starlette-admin` 비교표).
> 결론: **A1~A8 결정 대부분이 정설 부합**. 손볼 곳은 2개(인증 게이트·트리거 audit)뿐이고,
> SQLAdmin 미채택도 정당하다. 모두 추가형(잠긴 결정 뒤집기 없음).

**검증됨(변경 불필요 — 외부 근거로 확인):**
- **동일 스택·공용 데이터레이어**(A3): FastAPI 내장 + prod DB(CT110) 직접 read + 자체 복제 0 →
  내부툴 1위 정설("share the data layer, no copy")과 정확히 일치. 복제형 어드민이 달고 사는
  데이터 불일치 클래스를 통째로 회피.
- **내부 전용 API 분리**(A3·§1.2): `/admin/api/*` ≠ 모바일 `/v1`. "고객 API 위에 어드민 짓지
  마라(레이트리밋·숨김필드·벌크 부적합)"는 Yaro/Shipkit 만장일치 정설.
- **권위 소스 read-only 집계**(A5·§1.1): sync_runs/spots/users 직접 집계, 복사본 없음. juns
  소유 `sync_runs`를 alembic 밖 read-only로 둔 것도 스키마 소유권 충돌 회피의 정석.
- **조회 전용 우선 단계화**(A8): "overbuilding early"가 백오피스 1위 안티패턴 → Phase 1
  read-only(외부의존 0) 선출시는 교과서적.

### 9.1 SQLAdmin 미채택 — 모니터링≠CRUD라 정당 [검증됨]
- FastAPI 진영 사실상 표준은 SQLAdmin(모델→자동 CRUD)인데 A3은 **커스텀 정적 HTML** 선택.
  보통이면 "바퀴 재발명"이나 — **우리 3페이지(수집현황·이력·헬스)는 집계/모니터링 대시보드이지
  행 단위 CRUD가 아니다.** SQLAdmin의 격자 편집 UX와 부적합 → 커스텀 HTML이 정답.
- **차기 신호 주의(불요·메모)**: schema-docs "DB Atlas"가 curations/users/spots 테이블을
  들여다보려는 욕구의 전조. 향후 **테이블 직접 조회·편집** 니즈가 서면 `/admin/db`에 SQLAdmin을
  *별도 마운트*하는 하이브리드가 흔한 패턴(monitoring=커스텀, CRUD=SQLAdmin, 세션쿠키 분리).
  지금 도입은 불필요. 출처: aminalaee/sqladmin, benavlabs FastAPI-boilerplate(SQLAdmin /admin
  + SessionMiddleware), jowilf/starlette-admin 비교표.

### 9.2 A4 인증 게이트 강화 — 유일한 실 보안 약점 [추가형·우선]
- **근거**: 모든 소스가 "어드민은 **직원 SSO 또는 VPN/CIDR 뒤에**"로 일치(QuantLab "employee
  SSO", benavlabs "restrict /admin to VPN CIDR at proxy"). 우리는 **공개 도메인(api.pictrip.org)
  에 단일비번 HTTP Basic 한 겹** — RBAC 3역할 생략은 솔로 운영상 정당하나, *공개 인터넷 노출*
  자체가 다른 차원의 문제.
- **권고**: A4 Basic 위에 **Cloudflare Access**를 **Phase 1 필수로 승격**(스펙은 Phase 3 옵션에
  둠). 코드 0줄(CF 대시보드 설정)으로 이메일 OTP/SSO 게이트 → 솔로에겐 RBAC 풀스택보다 ROI
  압도적. Basic은 머신/스크립트 폴백으로 병행 유지. 출처: cloudflare zero-trust access,
  benavlabs admin-panel(proxy/VPN 제한 권장).

### 9.3 Phase 2 트리거에 audit log 1줄 — "쓰기엔 무조건 감사로그" [추가형]
- **근거**: "모든 write는 단일 함수 통과 + mutation 전 audit 이벤트 emit"이 만장일치
  정설(QuantLab 4번, Flatlogic core-essentials, hops.pub 백오피스 가이드). Phase 1은 read-only라
  N/A이나 **Phase 2 트리거가 유일한 쓰기** → 여기에만 적용하면 충분.
- **권고**: `POST /admin/api/collection/trigger` 성공/실패에 `누가(admin)·언제·job·결과
  (run_id/accepted)` 한 줄 기록(별 테이블 또는 구조화 로그). 풀 audit 인프라·RBAC는 솔로 3페이지
  엔 overbuilding이라 불요.

### 9.4 juns Streamlit 중복 — 역할분리가 정답 [검증됨·주의]
- 스펙 §6이 이미 인지(juns=파이프라인 내부 도구, 본 어드민=서비스측 헬스+수집 표면). "또 하나의
  고립된 툴 만들지 마라" 정설상 **역할분리 명문화가 옳은 해법**. 완전 겹치면 현황/이력을 juns
  대시보드 링크로 대체하는 폴백도 유지. 추가 조치 불요.

**적용(승인 후):** admin 스펙에 ① CF Access를 Phase 1 필수로 승격(§1.3 인증·§5 Phase 3 정정),
② Phase 2 트리거 audit 1줄을 §5 Phase 2 체크리스트에 추가, ③ SQLAdmin 하이브리드는 §6 리스크에
"차기 옵션" 메모로만. 모두 추가형이라 §7 승인 불요.

---

## 부록 — 리서치 출처(대표)
- CLIP/pgvector: theneuralbase.com/clip, ternaus/clip2classdist, arxiv 2411.05195, crunchydata
  HNSW, dbi-services pgvector, pgvector #609/#703, jkatz halfvec, AWS pgvector 0.8.
- Auth: OWASP ASVS V10, OWASP OAuth2 cheatsheet, Auth0 rotation, michal-drozd revocation,
  halodoc auth, supabase auth #2378, Apple/Google/Kakao OIDC 문서.
- 딥링크: Expo linking 문서(ios/android), Apple TN3155, forums 780496, shipnative.
- 피드: Airbnb GP(medium), Spotify HubFramework, Yelp CHAOS, DoorDash Facets, NYT niemanlab,
  redis thundering-herd, viprasol/dolthub polymorphic.
- 공모전/TourAPI: 공모문(scribd 1026171433·touraz.kr), github 1223v/Photoplace·thisis05·
  Isanghada, ASK2025 koCLIP, data.go.kr 15128555(집중률)·15101972(방문자), jpskill TourAPI.
- 관리자 콘솔: QuantLab internal-tools(2026), Yaro Labs SaaS admin-panel, Shipkit MVP admin,
  Flatlogic admin-development, hops.pub 백오피스, Let's Build Next.js admin, GitNexa dashboards,
  github aminalaee/sqladmin·SenZmaKi/spa-sqladmin·bankotij/rbac-admin-platform, benavlabs
  FastAPI-boilerplate admin-panel, jowilf/starlette-admin 비교표, cloudflare zero-trust access.
