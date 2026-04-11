# fz v3.8.0 Release Notes

> **Uncertainty-Aware Harness** — 모르는 것을 인정하고, 검증하고, 학습하는 시스템
> 2026-04-12

---

## 배경

PR-D1 플랜 v2를 Claude + Codex(GPT-5.4) 교차 리뷰하여 Claude blind spot 2건 발견:
- **B-1**: BehaviorRelay.accept()의 "thread-safe" ≠ downstream observer thread 보장
- **B-2**: receiveNightYn nil → "Y" 전송 = 기존에 안 보내던 필드를 명시적으로 추가 (omit ≠ default)

**근본 원인**: LLM이 모르는 것을 모른다고 말하지 않는다. 훈련 데이터의 확신 ≠ 검증된 사실.

v3.7.0의 Transformation Spec은 "무엇을 검증할지"만 정의했고, "검증 결과가 정확한지"는 보장하지 않았다.

---

## 신규

### `modules/uncertainty-verification.md` (66줄)

하네스 핵심 모듈. 모든 기술적 주장에 대한 검증 프로토콜.

핵심 개념:
- **Default-Deny**: `[verified: source]` 태그가 없는 기술적 주장은 자동 unverified. LLM의 자기 인식에 의존하지 않음.
- **Verification Cost Tiers**: Heavy(스레드/API계약, 3단계) / Light(일반, 코드+1소스) / Skip(코드 확인만)
- **Evidence Source Priority**: 코드(최고) > 테스트 > 공식 문서 > 훈련 데이터(최저)
- **Memory Feedback Loop**: 검증 실패 → 교훈 기록 → 다음 세션 로드 → 2건+ 시 규칙 승격
- **Pilot-first**: v3.8은 Transformation Spec 경로에서만 적용. 효과 확인 후 확장.

---

## 변경

### 모듈 개선 (2개)

| 모듈 | 변경 |
|------|------|
| `code-transform-validation.md` | Zero-Exception Thread Rule + Spec v3.8 (spec-version, 7번째 항목, [verified] 태그) + 마찰 신호(파라미터 키 불일치) + BEC/4-K fail-closed |
| `cross-validation.md` | spec-verify + confident-error + default-deny enforcement 게이트 3행 |

### 스킬 개선 (4개)

| 스킬 | 변경 | 줄 |
|------|------|:--:|
| `fz-plan` | Default-Deny [verified] 의무화 + Gate 1 체크리스트 | +7 |
| `fz-code` | BEC fail-closed + 파라미터 키 마찰 | +5 |
| `fz-review` | 4-K enforcement + Gate 4 + Harness Metrics | +22 |
| `fz-fix` | uncertainty-verification 참조 | +1 |

### Codex 스킬 개선 (2개)

| 스킬 | 변경 | 줄 |
|------|------|:--:|
| `fz-reviewer` | Zero-Exception + Default-Deny + Parameter | +9 |
| `fz-architect` | 동일 규칙 요약 | +3 |

---

## 하네스 엔지니어링 원칙 대응

| 원칙 | v3.8 대응 |
|------|----------|
| 원칙 1: 단순한 것부터 | 1 모듈 + 기존 구조에 추가만 |
| 원칙 2: 모델 변경 시 재검토 | spec-version으로 버전 관리 |
| 원칙 3: 경로를 좁히는가? | Default-Deny + fail-closed = 경로 좁힘 |
| 원칙 4: Generator ≠ Evaluator | Codex spec-verify + confident-error |
| 원칙 5: 점진적 진행 | Pilot → 확장 |
| Anti-Pattern 1: 과구조 | Pilot-first로 범위 제한 |

---

## 검증: PR-D1 이슈 잡히는가

| 이슈 | Plan | Code | Review |
|------|:----:|:----:|:------:|
| B-1: @MainActor | ✅ Default-Deny → Context7 → 기본값 | ✅ BEC fail-closed | ✅ thread_violation |
| B-2: nil→"Y" | ✅ Spec 파라미터 키 비교 | ✅ 마찰 신호 | ✅ parameter_addition |

**2/2 모두 3곳에서 잡힘.**

---

## Codex Adversarial 반영

| Codex 지적 | 반영 |
|-----------|------|
| Self-tagging 자기 의존 | Default-Deny (태그 없음 = unverified) |
| Policy without enforcement | BEC/4-K fail-closed Gate |
| Over-engineering | Pilot-first |
| 3단계 비용 과도 | Heavy/Light/Skip 계층화 |
| v3.7 마이그레이션 | spec-version 필드 + 하위 호환 |
| 검증 소스 우선순위 | 코드 > 테스트 > 문서 > 훈련 데이터 |

---

## 마이그레이션

추가 설정 불필요. 플러그인 업데이트 시 자동 적용.

- v3.7 Spec(spec-version 필드 없음)은 하위 호환 — 새 검증 항목 면제
- v3.8 Spec부터 [verified: source] 태그 의무화
- Harness Metrics는 fz-review 완료 보고에 자동 포함

---

## 후속 로드맵

| 버전 | 테마 |
|------|------|
| v3.9.0 | Pilot → 전체 확장 + Self-Evolution (교훈 2건+ → 규칙 승격) |
| v4.0.0 | Harness Ablation (Gate 기여도 데이터 기반 최적화) |
