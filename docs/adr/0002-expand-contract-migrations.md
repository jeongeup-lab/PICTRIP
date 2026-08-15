# 0002. 마이그레이션은 expand→contract, forward-only

- 상태: 채택
- 날짜: 2026-06-20
- 관련: `deploy/api-host/deploy.sh`, [deploy-and-release](../how-to/deploy-and-release.md)

## 맥락
`deploy.sh`의 롤백은 **컨테이너 이미지만** 되돌린다 — DB 마이그레이션은 되돌리지
않는다. 즉 롤백된 구 이미지가 새 스키마 위에서 실행된다. 파괴적 마이그레이션이
배포와 같은 리비전에 섞이면 롤백이 즉시 크래시를 만든다.

## 결정
**마이그레이션은 forward-only이고, 파괴적 변경(컬럼·테이블 드롭)은 해당 코드가
"롤백 대상 이미지"에서 이미 사라진 뒤에만 별도 리비전으로 낸다(expand→contract).**
autogenerate는 부분 인덱스·CHECK·드롭 downgrade를 놓치므로 SQL을 반드시 수동
리뷰한다.

## 고려한 대안
- **마이그레이션 롤백 지원** — halfvec·부분 인덱스가 얽힌 스키마에서 downgrade
  경로 유지 비용이 크고, 실전에서 신뢰할 수 없다. 기각.

## 결과
- 배포 실패 시 이미지 롤백만으로 안전하다.
- 테이블 보존 결정(예: `curations`)은 모델 삭제 + autogenerate `include_object`
  제외로 표현한다.
