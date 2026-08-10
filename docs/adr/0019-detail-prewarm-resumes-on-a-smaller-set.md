# 0019. 상세 프리워밍을 재개한다 — 모수가 5만이 아니라 1.2만이었다

- 상태: 채택
- 날짜: 2026-08-10
- 관련: [0014 여행 탭은 검색만 하지 않는다](0014-travel-tab-answers-not-only-searches.md),
  [0005 KTO 이미지 정책](0005-kto-image-policy.md),
  [architecture](../explanation/architecture.md),
  [crons-and-workflows](../reference/crons-and-workflows.md)

## 맥락

[0014](0014-travel-tab-answers-not-only-searches.md) 는 상세 프리워밍을 기각했다:

> **상세 프리워밍.** 5만 곳의 상세를 미리 채우면 라이브 콜이 사라진다. KTO 쿼터가
> 출시 후에나 증량되므로 지금은 불가능하고, 96.7%를 채우는 데 드는 콜 수가 일일
> 한도를 넘는다.

2026-08-10 `agent-detail-coverage` 프로브로 실측하니 전제가 틀렸다.

- 여행 탭이 실제로 서빙하는 모수는 5만이 아니라 **11,575곳** 이다. `show_flag = 1`
  · 대표이미지 보유 · attraction 술어를 통과한 집합이고, 0014 는 `spots` 전체를
  기준으로 셌다.
- 그중 `spot_details` 캐시는 **9.2%**(1,069곳)뿐이다. 나머지 90.8% 는 정보 질문이
  들어오면 `load_spot_detail` 이 KTO 3콜을 동기로 부른다(예산 8초). 게이트웨이가
  요청 절반 이상을 4~8초 붙잡으므로 대기 아니면 "지금은 확인이 어려워요" 로 끝난다.
- 갤러리 centroid 백필이 2026-08-09 완주했다(`targets=0`). 하루 800콜을 쓰던
  06:00 슬롯이 통째로 비었다.

11,575 ÷ 800 ≈ **15일**. 1차 마감(2026-09-21)까지 42일이 남아 있다.

## 결정

**`detailCommon2` 1콜만 쓰는 프리워밍을 재개한다.** 갤러리 백필이 비운 06:00 크론
슬롯에서 하루 800스팟씩, `overview` 가 채워진 스팟은 다음 실행 대상에서 빠지는
resumable 잡이다(`detail-prewarm.yml` · `scripts/prewarm_details.py`).

**`detailIntro2` 는 프리워밍하지 않는다.** 2콜로 늘리면 29일이 걸려 다른 백필이
슬롯에 들어올 수 없는데, 얻는 것이 빈약하다 — 같은 프로브에서 `usetime` 의 56% 가
"상시 개방", `parking` 의 91% 가 "가능"/"불가능" 한 단어, `usefee` 는 유효율 0.9%
(content_type_id 12 에서 0.0%)였다. `overview` 는 산문이고 상세 화면
`IntroSection` 까지 같이 채운다.

**프리워밍은 전용 쓰기 경로를 쓴다.** `_persist_detail` 을 그대로 태우면 두 가지를
지운다 — `replace_spot_images([])` 가 `sort_order >= 0` 을 전삭제해 방금 완주한
갤러리를 날리고, `intro_data=None` 이 기존 intro 를 덮어쓴다. `persist_detail_common`
은 `overview`/`homepage`/`tel`/`cached_at` 만 upsert 하고 나머지 컬럼과
`spot_images` 를 건드리지 않는다.

**신선도는 intro 를 인지한다.** 프리워밍이 만든 행은 `intro_data` 가 NULL 인 채
`cached_at` 이 최신이라, 그대로 두면 90일 동안 "fresh" 로 판정돼 intro 라이브
조회를 막는다. `load_spot_detail(require_intro=True)` 는 `intro_data IS NULL` 을
미충족으로 보고 라이브 조회로 내려간다. 에이전트는 `overview` 외의 필드를 물을
때만 이 플래그를 켠다.

## 결과

- 15일 뒤 `overview` 커버리지가 9.2% → 100% 에 수렴한다. "여긴 어떤 곳이야?" 와
  상세 화면 진입이 KTO 를 타지 않는다.
- 영업시간·주차·요금 질문은 여전히 캐시 미스 시 KTO 를 탄다. 프리워밍 이전과 같은
  비용이므로 회귀는 없다.
- 06:00 슬롯이 15일간 점유된다. 그 사이 다른 KTO 백필은 쿼터 헤드룸(~200콜) 안에서만
  돌 수 있다.
- 프리워밍이 끝나면 잡은 사실상 no-op 이 된다(신규·변경 스팟만 잡힘).

## 고려한 대안

**2콜 프리워밍(`detailCommon2` + `detailIntro2`).** 29일이 걸리고, 얻는 값의 절반
이상이 "상시 개방"·"가능" 이다. 쿼터가 증량되면 그때 다시 본다.

**정보 칩을 캐시 보유 스팟에서만 노출.** 프리워밍 없이 즉시 대기·실패를 없앨 수
있지만, 커버리지가 9.2% 라 칩이 거의 보이지 않는다. 칩이 나타났다 사라졌다 해서
예측 가능성도 떨어진다.

**`_persist_detail` 재사용 + 이미지 재조회.** 갤러리를 지웠다가 다시 채우려면
`detailImage2` 가 붙어 콜이 2배가 된다. 전용 upsert 가 싸다.

---

관련: [0014](0014-travel-tab-answers-not-only-searches.md) ·
[architecture](../explanation/architecture.md)
