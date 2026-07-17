# 0004. 홈 = 해외 사진 피드 → 국내 매칭 (S13)

- 상태: 채택
- 날짜: 2026-07-12
- 관련: [product](../explanation/product.md), [architecture](../explanation/architecture.md)

## 맥락
구 제품은 "큐레이션 홈(`/home/feed` 히어로+레일) + 사진 업로드 검색
(`/taste/photo-search`)"이었다. 업로드 검색은 사용자가 먼저 좋은 사진을 가져와야
하는 마찰이 크고, 큐레이션은 운영 손이 계속 들어간다.

## 결정
**해외 여행 사진 피드를 구경하다 스와이프하면 닮은 국내 관광지 3곳을 보여주는
"발견 → 매칭" 루프로 전환한다.** `/feed`·`/explore`·`/overseas/{id}/matches`·
`/home/channels`를 신설하고, `taste` 모듈·`/home/feed`·`/curations/{slug}`·어드민
큐레이션 편집기를 제거한다. `curations`/`curation_spots` 테이블은 보존한다.
매칭은 CLIP 코사인 거리(`MATCH_DISTANCE_MAX=0.32`), 해외 원천은 Wikidata+Commons
2,347행. 유사도 수치는 UI에 노출하지 않는다(과장 방지 — 순번만).

## 고려한 대안
- **사진 업로드 검색 유지·개선** — 콜드스타트 마찰이 본질이라 기각.
- **큐레이션 자동화** — 운영 대상(콘텐츠)이 아니라 매칭 엔진에 투자. 기각.

## 결과
- 모듈 구성은 `users·spots·feed·images·map·system·admin` 7개로 정정.
- 구 큐레이션 공유 링크는 `web/_redirects`의 `/curations/* → /` 302로 착지.
- 매칭 품질은 attraction 버킷 게이트 + 갤러리 centroid 임베딩으로 후속 보강
  (2026-07-17 라이브).
