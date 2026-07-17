# 배포·릴리스

> 목표: 변경을 올바른 레일(자동 배포·OTA·네이티브 빌드)로 안전하게 내보낸다.

## 전제
- **dev 머지 = 즉시 라이브. 스테이징 없다.** PR 리뷰·검증이 마지막 관문이다.
- 브랜치는 dev에서 짧게, 당일 머지. 머지 방식은 rebase merge만.

## 단계

1. **백엔드/파이프라인 변경** — dev 머지가 곧 배포다.
   `backend-deploy.yml`: test → GHCR 이미지 → CT112 `deploy.sh`(pull → up,
   entrypoint가 `alembic upgrade head` → 스모크 → 실패 시 **이미지만** 롤백).
   ```bash
   gh run watch $(gh run list --workflow backend-deploy.yml --branch dev --limit 1 --json databaseId --jq '.[0].databaseId')
   curl -s https://api.pictrip.org/health
   ```

2. **모바일 JS 변경** — dev 머지가 EAS OTA를 쏜다(`mobile-ota.yml`).
   fingerprint 가드: 네이티브 지문이 일치하는 설치본에만 전달된다.

3. **모바일 네이티브 변경** (모듈·권한·SDK) — OTA로는 **조용히 무시**된다.
   main으로 릴리스 PR → `v*` 태그 → `mobile-deploy.yml`이 TestFlight 빌드·제출.
   ```bash
   git tag v0.7.0 && git push origin v0.7.0
   ```

4. **web 변경** — main 푸시 시 CF Pages 자동 빌드(root=`web/`).

## 검증
- 백엔드: `/health` ok + 대표 엔드포인트 1개 프로브.
- OTA: EAS 대시보드에서 update가 브랜치(=빌드 프로파일명)에 게시됐는지.
- 네이티브: TestFlight 처리 완료 메일.

## 자주 나는 문제
| 증상 | 원인 | 해결 |
|---|---|---|
| OTA 후 소셜 로그인 전멸 | `eas update`는 러너 env로 번들 — `EXPO_PUBLIC_*` 미주입 | `mobile-ota.yml`의 주입 스텝이 정상인지 확인. **절대 로컬에서 맨 `eas update` 금지** |
| 네이티브 변경이 반영 안 됨 | OTA만 나감(fingerprint skip) | `v*` 태그로 빌드 |
| 배포 실패 `no space left` | CT112 디스크 풀 | `pct exec 112 -- docker builder prune -af && docker image prune -af` 후 `gh run rerun --failed` |
| 마이그레이션 얽힌 롤백 | 롤백은 이미지만 | expand→contract(→ [ADR-0002](../adr/0002-expand-contract-migrations.md)) |

---
관련: [run-the-backend](run-the-backend.md) · [run-the-mobile-app](run-the-mobile-app.md) · [crons-and-workflows](../reference/crons-and-workflows.md)
