# PicTrip 문서

코드와 함께 버전관리되는 엔지니어링 문서(docs-as-code). [Diátaxis](https://diataxis.fr) 4분류로 목적에 따라 찾는다.

| 원하는 것     | 폴더                         | 문서                                                                                                                                                                                                                                                                                            |
| ------------- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **이해하기**  | [explanation/](explanation/) | [architecture](explanation/architecture.md) · [product](explanation/product.md) · [data-model](explanation/data-model.md) · [glossary](explanation/glossary.md)                                                                                                                                 |
| **작업하기**  | [how-to/](how-to/)           | [run-the-backend](how-to/run-the-backend.md) · [run-the-mobile-app](how-to/run-the-mobile-app.md) · [qa-travel-tab](how-to/qa-travel-tab.md) · [verify-travel-chat](how-to/verify-travel-chat.md) · [deploy-and-release](how-to/deploy-and-release.md) · [operate-embeddings](how-to/operate-embeddings.md) · [inspect-prod](how-to/inspect-prod.md) |
| **찾아보기**  | [reference/](reference/)     | [api](reference/api.md) · [database-schema](reference/database-schema.md) · [crons-and-workflows](reference/crons-and-workflows.md) · [cli](reference/cli.md) · [admin-console](reference/admin-console.md) · [travel-tab](reference/travel-tab.md)                                             |
| **계획**      |                              | [todo](todo.md)                                                                                                                                                                                                                                                                                 |
| **결정 이력** | [adr/](adr/)                 | 채택 후 불변 — 뒤집으면 새 ADR로 대체                                                                                                                                                                                                                                                           |

개발 규칙·금지사항의 SSOT는 루트 [`CLAUDE.md`](../CLAUDE.md), 유닛 로컬 요약은
[`pipeline/README.md`](../pipeline/README.md).

## 문서 작성 규칙

- **제목 → `>` 한 줄 목적문 → 타입별 섹션 → `---` 관련 링크** 순서.
- 타입별 구조: explanation(맥락→핵심 개념→어떻게 맞물리나→설계 근거) ·
  how-to(목표→전제→단계→검증→자주 나는 문제) · reference(표 중심).
- 원칙 셋: **현행만 기록한다** (히스토리는 ADR+git) · **코드로 알 수 있는 것은
  쓰지 않는다** (문서는 지도) · **문서당 하나의 질문에 답한다**.
- 한글 본문·용어 보존, 코드/명령은 영어.

## 새 ADR

번호 순차(`NNNN-제목.md`), 한 파일 1결정. 채택 후 본문 불변 — 바뀌면 새 ADR로
대체하고 구 ADR 상태를 "대체됨"으로 표기. 형식: 상태·날짜·관련 → 맥락 → 결정 →
고려한 대안 → 결과.
