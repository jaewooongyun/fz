# 빌드 검증

> fz- 스킬의 빌드 검증 공통 모듈. 프로젝트 무관 범용.

## 빌드 명령 결정

1. CLAUDE.md `## Build` 섹션에 정의된 빌드 도구/명령 (최우선)
2. CLAUDE.md 도구 매칭:
   - XcodeBuildMCP 명시 → `mcp__XcodeBuildMCP__build_sim` 우선
   - xcodebuild 명시 → `xcodebuild` 직접 실행
   - npm/yarn 명시 → `npm run build` / `yarn build`
   - cargo 명시 → `cargo build`
   - gradle 명시 → `./gradlew build`
3. 도구 미명시 → AskUserQuestion("빌드 명령을 알려주세요")

## 빌드 검증 절차

1. 빌드 명령 결정 (위 우선순위)
2. Clean Build 판단: 메서드/함수 시그니처 변경(파라미터 추가/제거/타입 변경)이 포함된 경우 → clean build 실행. 이유: incremental build 캐시가 변경되지 않은 파일의 적합성 검사를 생략할 수 있음
   - xcodebuild: `mcp__XcodeBuildMCP__clean` 후 빌드, 또는 `xcodebuild clean build`
   - npm/yarn: `rm -rf node_modules/.cache && npm run build`
   - cargo: `cargo clean && cargo build`
   - 기타: CLAUDE.md에 clean 명령이 있으면 사용
3. 빌드 실행
4. 에러 분석 → 수정 → 재빌드 (최대 3회)
5. 3회 실패 시 사용자 에스컬레이션

## 에러 유형별 대응

심볼 도구(Serena)를 우선 활용하여 빌드 에러를 해결한다 — 시그니처 확인, import 추가, 정의 위치 탐색 등.
Serena 불가 시 Edit + Grep으로 폴백.

## 빌드-수정 반복 패턴

점진적 에스컬레이션: 직접 수정 → 자동 진단(/sc:troubleshoot) → 사용자 에스컬레이션 (최대 3회)

## 조건부 테스트 게이트

코드 변경과 관련된 테스트가 존재하는 경우, 빌드 성공 후 테스트도 실행한다.

| 조건 | 행동 |
|------|------|
| 변경 파일에 대응하는 테스트 파일 존재 | 해당 테스트 실행 |
| 테스트 파일 자체를 수정 | 해당 테스트 실행 |
| 테스트 파일 없음 | 빌드 검증만 (테스트 스킵) |

테스트 실행 명령: CLAUDE.md `## Build` 섹션의 테스트 명령 우선. 미정의 시 빌드 도구에 따라 자동 결정.

## Gate 체크리스트

- [ ] 빌드 성공?
- [ ] 빌드 경고 최소화?
- [ ] 관련 테스트 통과? (테스트 존재 시)

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-code | 매 Step 구현 후 빌드 검증 |
| /fz-fix | 수정 후 빌드 검증 |
| /fz-review | 리뷰 전 빌드 상태 확인 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
