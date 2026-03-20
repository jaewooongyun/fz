---
name: fz-recording
description: >-
  This skill should be used when the user has an audio recording or transcript to turn into meeting notes.
  Make sure to use this skill whenever the user says: "녹음", "회의록", "화자 분리",
  "recording", "meeting notes", "transcribe".
  Covers: 녹음 파일, 회의록, 화자 분리, STT, 음성 변환, AI 첨언, AssemblyAI.
  Do NOT use for code-related tasks (use fz-code, fz-fix).
user-invocable: true
argument-hint: "<audio-file> [--text <transcript>] [--speakers \"이름1,이름2\"]"
allowed-tools: >-
  Read, Write, Bash(curl *), Bash(jq *), Bash(command -v *)
composable: false
provides: [documentation]
needs: [none]
intent-triggers:
  - "녹음|회의록|녹취|화자|분리|STT|음성"
  - "recording|meeting.*notes|transcri|diariz|speaker"
model-strategy:
  main: opus
  verifier: null
compatibility: >-
  macOS, AssemblyAI API key (무료 185시간), jq, curl
---

# /fz-recording — 녹음 파일 화자 분리 + 회의록 생성 스킬

> **행동 원칙**: 오디오 녹음 파일을 AssemblyAI(STT+화자분리)로 처리하고, Claude가 구조화된 회의록을 생성한다. 회의록 생성 후 Claude가 회의 내용을 분석하여 첨언(인사이트, 리스크, 제안)을 `> [!AI 첨언]` 블록으로 추가한다. 텍스트만 제공 시 Claude가 문맥 기반으로 화자를 추론한다.

## 개요

```
Audio(.m4a/.mp3/...) → AssemblyAI(STT+Diarization) → Claude(회의록) → Claude(AI 첨언) → 회의록.md
Text only (폴백)     → Claude(화자 추론+회의록)     → Claude(AI 첨언) → 회의록.md
```

- **AssemblyAI 무료 티어**: 185시간 무료, 한국어 지원, 전문 화자 분리
- **2가지 입력 모드**: 오디오(권장) / 텍스트만(폴백)
- **회의록 출력**: 참석자, 안건, 논의, 결정사항, 액션 아이템
- **AI 첨언**: 회의록 각 섹션과 말미에 Claude의 분석/인사이트를 `> [!AI 첨언]` 블록으로 명시 삽입

## 사용 시점

```bash
/fz-recording meeting.m4a                          # 오디오만 → 자동 STT + 화자 분리
/fz-recording meeting.m4a --text transcript.txt     # 오디오 + 참조 텍스트
/fz-recording --text transcript.txt                 # 텍스트만 (폴백 모드)
/fz-recording meeting.m4a --speakers "김팀장,이대리,박사원"  # 화자 이름 지정
/fz-recording --setup                               # API 키 설정 가이드
```

---

## 사전 요구사항

| 항목 | 설명 | 필수 |
|------|------|------|
| AssemblyAI API 키 | 환경변수 `ASSEMBLYAI_API_KEY` 또는 `~/.config/fz-recording/config` | 오디오 모드 시 필수 |
| jq | JSON 파싱용 CLI 도구 (`brew install jq`) | 오디오 모드 시 필수 |
| curl | HTTP 요청 (macOS 기본 포함) | 오디오 모드 시 필수 |
| 오디오 파일 | .m4a, .mp3, .wav, .webm, .flac, .ogg 등 | 오디오 모드 시 필수 |
| 텍스트 파일 | 이미 변환된 녹취 텍스트 (.txt) | 텍스트 모드 시 필수 |

### API 키 발급 (무료)

1. https://www.assemblyai.com 가입 (이메일만으로 가능)
2. Dashboard → API Keys에서 키 복사
3. 아래 중 하나로 설정:

```bash
# 방법 1: 환경변수 (권장)
echo 'export ASSEMBLYAI_API_KEY="your-key-here"' >> ~/.zshrc
source ~/.zshrc

# 방법 2: 설정 파일
mkdir -p ~/.config/fz-recording
echo "your-key-here" > ~/.config/fz-recording/config
```

---

## Phase 1: Input Validation

### 절차

1. **API 키 확인**:
   ```bash
   # 환경변수 우선, 없으면 설정 파일
   API_KEY="${ASSEMBLYAI_API_KEY:-$(cat ~/.config/fz-recording/config 2>/dev/null)}"
   ```
   - API 키 없음 + 오디오 모드 → `--setup` 가이드 출력 후 중단
   - API 키 없음 + 텍스트만 → 폴백 모드로 진행

2. **입력 파일 확인**:
   - 오디오 파일: 존재 여부 + 지원 형식 확인
   - 텍스트 파일: 존재 여부 + 내용 읽기
   - 둘 다 없음 → 에러

3. **의존성 확인** (오디오 모드):
   ```bash
   command -v jq >/dev/null || echo "jq 필요: brew install jq"
   command -v curl >/dev/null || echo "curl 필요"
   ```

4. **모드 결정**:
   - 오디오 있음 → **Full Mode** (AssemblyAI STT + 화자 분리)
   - 텍스트만 → **Fallback Mode** (Claude 화자 추론)

### Gate 1: Input Ready
- [ ] 입력 파일(오디오 또는 텍스트)이 존재하는가?
- [ ] Full Mode 시 API 키 + jq가 준비되었는가?
- [ ] 실행 모드(Full/Fallback)가 결정되었는가?

---

## Phase 2: Speaker Diarization (Full Mode)

AssemblyAI API로 오디오를 업로드하고 STT + 화자 분리를 수행합니다.

### 절차

1. **오디오 업로드**:
   ```bash
   UPLOAD_URL=$(curl -s -X POST "https://api.assemblyai.com/v2/upload" \
     -H "authorization: $API_KEY" \
     --data-binary @"$AUDIO_FILE" | jq -r '.upload_url')
   ```

2. **Transcription + Diarization 요청**:
   ```bash
   TRANSCRIPT_ID=$(curl -s -X POST "https://api.assemblyai.com/v2/transcript" \
     -H "authorization: $API_KEY" \
     -H "content-type: application/json" \
     -d "{
       \"audio_url\": \"$UPLOAD_URL\",
       \"speaker_labels\": true,
       \"speech_models\": [\"universal-3-pro\", \"universal-2\"],
       \"language_code\": \"ko\"
     }" | jq -r '.id')
   ```

3. **완료 대기 (polling)**:
   ```bash
   while true; do
     RESULT=$(curl -s "https://api.assemblyai.com/v2/transcript/$TRANSCRIPT_ID" \
       -H "authorization: $API_KEY")
     STATUS=$(echo "$RESULT" | jq -r '.status')
     if [ "$STATUS" = "completed" ] || [ "$STATUS" = "error" ]; then break; fi
     sleep 5
   done
   ```

4. **결과 파싱**:
   ```bash
   # 화자별 발화 추출
   echo "$RESULT" | jq -r '.utterances[] | "Speaker \(.speaker) (\(.start/1000|floor)s): \(.text)"'
   ```

   AssemblyAI 응답 구조:
   ```json
   {
     "utterances": [
       {"speaker": "A", "text": "안녕하세요", "start": 0, "end": 1500},
       {"speaker": "B", "text": "네, 반갑습니다", "start": 1600, "end": 3200}
     ]
   }
   ```

### Gate 2: Diarization Complete
- [ ] AssemblyAI 응답 status가 "completed"인가?
- [ ] utterances 배열에 화자 라벨이 포함되어 있는가?
- [ ] 에러 시 → Phase 2F(Fallback)로 전환

---

## Phase 2F: Claude 화자 추론 (Fallback Mode)

텍스트만 제공된 경우, Claude가 문맥 기반으로 화자를 추론합니다.

### 절차

1. 텍스트 파일 읽기
2. 화자 교체 신호 분석:
   - 문장 어미 변화 (존댓말 ↔ 반말)
   - 질문 → 답변 패턴
   - 주제 전환
   - "네", "아", "그런데" 등 응답 신호
3. 추론 결과에 신뢰도 표시: `[확실]` / `[추정]`

### 한계 고지

텍스트만으로는 화자 분리 정확도가 낮습니다. 정확한 결과를 위해 오디오 파일 제공을 권장합니다.

---

## Phase 3: Meeting Notes Generation

Claude가 화자별 발화 데이터를 구조화된 회의록으로 변환합니다.

### 절차

1. **화자 이름 매핑** (--speakers 옵션 제공 시):
   - Speaker A → 김팀장, Speaker B → 이대리, ...
   - 미제공 시 → Speaker A, Speaker B 유지

2. **회의록 생성** — 아래 형식으로:

   ```markdown
   # 회의록 — {주제}

   ## 기본 정보
   - **일시**: {파일 수정일 또는 사용자 입력}
   - **참석자**: {화자 목록}
   - **녹음 시간**: {duration}

   ## 회의 배경
   {회의가 열린 맥락, 배경 설명 — 대화 내용에서 추론}

   ## 1. {안건 주제}

   ### 배경
   {이 안건이 논의된 이유}

   ### 결정
   > {합의된 결정 사항 — blockquote로 강조}

   ### 주요 논점
   - **{화자A}**: {발언 요약}
   - **{화자B}**: {응답 요약}

   > [!AI 첨언]
   > {Claude가 추론한 인사이트, 리스크, 놓친 관점, 제안 등}

   ## 결정사항 요약
   | # | 결정 | 상세 |
   |---|------|------|
   | 1 | {결정 제목} | {결정 내용} |

   ## 액션 아이템
   | 담당 | 내용 | 기한 |
   |------|------|------|
   | {화자A} | {할 일} | {언급된 기한} |

   ## 미결 사항
   1. {추후 논의 필요한 항목 — 대화에서 결론 안 난 것}

   ---

   ## AI 종합 분석

   > [!AI 첨언 — 종합]
   > ### 회의 효과성
   > {회의 진행, 합의 도출, 시간 활용 등에 대한 분석}
   >
   > ### 잠재 리스크
   > {결정사항에서 놓칠 수 있는 리스크, 의존성, 맹점}
   >
   > ### 추가 제안
   > {논의되지 않았지만 고려할 만한 사항}
   ```

3. **참조 텍스트 활용** (--text 제공 시):
   - AssemblyAI STT 결과와 사용자 텍스트를 비교
   - 고유명사, 전문용어 등에서 사용자 텍스트가 더 정확하면 반영

### Gate 3: Notes Generated
- [ ] 회의록에 배경, 안건별 논의, 결정사항, 액션 아이템이 모두 포함되었는가?
- [ ] 화자 이름이 올바르게 매핑되었는가?
- [ ] 미결 사항이 식별되었는가?

---

## Phase 3.5: AI Commentary (Claude 첨언)

회의록 생성 후, Claude가 회의 내용을 분석하여 **인사이트, 리스크, 제안**을 첨언합니다.
모든 첨언은 `> [!AI 첨언]` blockquote로 래핑하여 **사실(회의 내용)과 추론(Claude 분석)을 명확히 구분**합니다.

### 첨언 삽입 위치

| 위치 | 첨언 유형 | 설명 |
|------|----------|------|
| **각 안건 끝** | 인라인 첨언 | 해당 안건에 대한 구체적 인사이트 |
| **문서 말미** | 종합 분석 | 회의 전체에 대한 메타 분석 |

### 인라인 첨언 — 각 안건별

각 안건의 "주요 논점" 아래에 삽입. 아래 관점 중 해당하는 것만 선택:

| 관점 | 설명 | 예시 |
|------|------|------|
| **놓친 관점** | 논의에서 언급되지 않았지만 고려할 만한 것 | "데이터 마이그레이션 계획이 논의되지 않았음" |
| **잠재 리스크** | 결정의 부작용이나 의존성 | "iOS 17 상향 시 CI/CD 파이프라인 수정 필요" |
| **실행 장애물** | 결정을 실행할 때 예상되는 어려움 | "모듈 분리 시 빌드 시간 증가 가능성" |
| **관련 맥락** | 업계 트렌드, 유사 사례, 기술적 배경 | "Google도 Compose 전환에 2년 소요" |
| **구체화 제안** | 결정이 추상적일 때 실행 방안 제시 | "POC 범위를 PR 20개 이하 변경으로 제한 권장" |

형식:
```markdown
> [!AI 첨언]
> **놓친 관점**: {내용}
> **잠재 리스크**: {내용}
```

### 종합 분석 — 문서 말미

3가지 축으로 분석:

1. **회의 효과성**: 안건 소화율, 합의 도출 비율, 시간 활용
2. **잠재 리스크**: 결정사항들의 교차 영향, 의존성, 맹점
3. **추가 제안**: 논의되지 않았지만 후속으로 다루면 좋을 주제

### 첨언 작성 원칙

1. **사실과 추론 분리**: 회의에서 실제 나온 말 vs Claude의 분석을 구분. 첨언 블록 밖에는 추론을 넣지 않음
2. **겸손한 어조**: "~일 수 있음", "~를 고려해볼 만함" (단정 X)
3. **관련성 필터**: 해당 안건과 직접 관련 있는 것만. 억지 첨언 금지
4. **비어있으면 생략**: 특별한 인사이트가 없는 안건에는 첨언을 넣지 않음

### Gate 3.5: Commentary Added
- [ ] 각 안건별 첨언이 `> [!AI 첨언]` 형식인가?
- [ ] 종합 분석에 효과성/리스크/제안 3축이 포함되었는가?
- [ ] 사실과 추론이 혼동되지 않았는가?
- [ ] 불필요한 억지 첨언이 없는가?

---

## Phase 4: Output

### 절차

1. **파일 저장**:
   - 기본 경로: `{오디오파일명}_회의록.md`
   - 예: `meeting.m4a` → `meeting_회의록.md`
   - 텍스트 모드: `{텍스트파일명}_회의록.md`

2. **요약 출력**:
   ```markdown
   /fz-recording 완료

   **입력**: {파일명} ({duration})
   **모드**: Full (AssemblyAI) / Fallback (텍스트만)
   **화자**: {N}명 감지 — {화자 목록}
   **출력**: {출력파일 경로}

   **요약**: {1-2줄 회의 핵심 요약}
   ```

---

## Few-shot Example

```
입력: weekly_standup.m4a --speakers "김PM,이개발,박디자인"

출력 (weekly_standup_회의록.md):
# 회의록 — 주간 스탠드업

## 기본 정보
- **일시**: 2026-03-06
- **참석자**: 김PM, 이개발, 박디자인
- **녹음 시간**: 23분 15초

## 회의 배경
스프린트 2주차 중간 점검. 로그인 기능 완료 후 결제 모듈로 전환하는 시점.

## 1. 스프린트 진행 현황

### 배경
이번 스프린트 목표: 로그인 + 결제 모듈 완료

### 결정
> 결제 모듈 금요일 마감 유지. 우선순위 변경 없음.

### 주요 논점
- **김PM**: 목표 달성률 80%. 로그인 완료. 결제가 남은 핵심.
- **이개발**: 결제 API 연동 중. PG사 테스트 환경 세팅 완료. 금요일 목표.
- **합의**: 결제 우선순위 유지, 디자인 리뷰는 목요일로 이동

> [!AI 첨언]
> **잠재 리스크**: PG사 테스트 환경이 실결제와 차이가 있을 수 있어, QA 시간을 별도 확보하는 것이 안전할 수 있음.
> **구체화 제안**: 금요일 완료 후 주말 전 smoke test 일정을 잡아두면 월요일 이슈 대응에 유리.

## 결정사항 요약
| # | 결정 | 상세 |
|---|------|------|
| 1 | 결제 모듈 마감 | 금요일 유지 |
| 2 | UI 리뷰 일정 | 목요일 오후 |

## 액션 아이템
| 담당 | 내용 | 기한 |
|------|------|------|
| 이개발 | 결제 API 연동 완료 | 금요일 |
| 박디자인 | 로그인 화면 최종안 공유 | 수요일 |

## 미결 사항
1. QA 일정 미확정 — 결제 완료 후 별도 논의 필요

---

## AI 종합 분석

> [!AI 첨언 — 종합]
> ### 회의 효과성
> 23분 내 3개 안건 소화. 핵심 마감은 유지로 빠르게 합의.
>
> ### 잠재 리스크
> 결제 모듈 금요일 마감이 촉박할 경우 UI 리뷰(목요일)와 충돌 가능성.
>
> ### 추가 제안
> 다음 스탠드업에서 결제 모듈 진행률 중간 체크(수요일)를 추가하면 리스크 조기 감지에 도움.
```

---

## 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "회의 녹음 파일 정리해줘" | trigger | 일반 케이스 |
| "이 녹취록 회의록으로 만들어줘" | trigger | 텍스트 모드 |
| "meeting.m4a 화자 분리해줘" | trigger | 화자 분리 키워드 |
| "코드 리뷰해줘" | NOT trigger | → fz-review |
| "버그 수정해줘" | NOT trigger | → fz-fix |

### Functional

| Given | When | Then |
|-------|------|------|
| 오디오 + API 키 | `/fz-recording meeting.m4a` | AssemblyAI STT + 회의록 생성 |
| 텍스트만 | `/fz-recording --text transcript.txt` | Claude 화자 추론 + 회의록 생성 |
| API 키 없음 + 오디오 | `/fz-recording meeting.m4a` | `--setup` 가이드 출력 |
| 오디오 + 화자 이름 | `/fz-recording meeting.m4a --speakers "A,B"` | 화자 매핑된 회의록 |

---

## Boundaries

**Will**:
- 오디오 → AssemblyAI STT + 화자 분리 → 회의록 생성
- 텍스트만으로 화자 추론 (폴백)
- 화자 이름 매핑
- 회의록 마크다운 파일 생성 (안건별 상세 구조)
- 회의 내용에 대한 AI 첨언 삽입 (인사이트, 리스크, 제안 — `> [!AI 첨언]` 블록)
- API 키 설정 가이드 제공

**Will Not**:
- 실시간 녹음 → 별도 녹음 앱 사용
- 영상 파일 처리 → 오디오만 추출 후 사용
- 번역 → 한국어 녹음 → 한국어 회의록 (동일 언어)
- 코드 관련 작업 → `/fz-code`, `/fz-fix` 사용

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| API 키 미설정 | `--setup` 가이드 출력 | 텍스트 모드로 전환 제안 |
| jq 미설치 | `brew install jq` 안내 | Python json 모듈 사용 |
| AssemblyAI 업로드 실패 | 파일 크기/형식 확인 안내 | 텍스트 모드 전환 제안 |
| AssemblyAI 처리 에러 | 에러 메시지 출력 + 재시도 | 텍스트 모드 전환 |
| 화자 1명만 감지 | 사용자에게 확인 (1인 독백?) | 화자 분리 없이 요약만 |
| 긴 녹음 (2시간+) | 정상 처리 (무료 185시간 한도 안내) | — |
| 오디오 품질 낮음 | STT 정확도 저하 경고 + 결과 출력 | 사용자 텍스트 참조 제안 |

## Completion → Next

- 회의록 생성 완료 → 파일 경로 안내
- 추가 녹음 정리 → `/fz-recording` 재실행
- 회의록 기반 작업 → 수동 확인 후 진행
