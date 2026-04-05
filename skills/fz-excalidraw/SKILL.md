---
name: fz-excalidraw
description: >-
  This skill should be used when the user wants to create or edit visual diagrams.
  Make sure to use this skill whenever the user says: "다이어그램 그려줘", "시각화해줘",
  "구조도 만들어줘", "플로우차트 그려줘", "흐름도 그려줘", "아키텍처 그림", "도식화해줘",
  "draw a diagram", "visualize this", "create a flowchart", "show me the architecture",
  "draw the structure", "excalidraw".
  Covers: 다이어그램, 그려줘, 시각화, 구조도, 플로우차트, 흐름도, 아키텍처 도식, Excalidraw JSON 생성/수정.
  Do NOT use for Mermaid/PlantUML output, or pure code tasks without visualization need.
user-invocable: true
argument-hint: "[다이어그램 설명] 또는 [기존 .excalidraw 파일 경로 + 업데이트 내용]"
allowed-tools: >-
  Read, Write, Edit, Glob, Grep,
  Bash(uv run python *),
  Bash(uv sync),
  Bash(uv run playwright *)
composable: true
provides: [diagram]
needs: [none]
intent-triggers:
  - "다이어그램|그려줘|시각화|구조도|플로우차트|흐름도|아키텍처.*그림|도식화"
  - "diagram|excalidraw|visualize|draw|flowchart|architecture.*diagram"
model-strategy:
  main: opus
  verifier: null
---

# /fz-excalidraw — Excalidraw 다이어그램 스킬

> **행동 원칙**: 다이어그램은 정보를 나열하지 않고 시각적으로 논증한다. JSON을 생성한 후 반드시 렌더링하여 눈으로 확인하고 수정한다.

## 참조 파일 (작업 전 반드시 읽기)

| 파일 | 목적 | 읽는 시점 |
|------|------|----------|
| `references/color-palette.md` | 모든 색상의 단일 진실 소스 | **JSON 생성 전 필수** |
| `references/element-templates.md` | copy-paste JSON 템플릿 | 요소 생성 시 |
| `references/diagram_utils.py` | Python 헬퍼 모음 (30+ 요소 시 권장) | Python 스크립트 생성 시 |

---

## Phase 1: 다이어그램 설계

### 1-1. 깊이 판단 (먼저)

| 타입 | 조건 | 방식 |
|------|------|------|
| Simple/Conceptual | 멘탈 모델, 철학, 추상 개념 | 추상 도형 |
| Technical | 실제 시스템, 프로토콜, 아키텍처 | 구체적 예시 + Evidence Artifacts 필수 |

기술 다이어그램이면 **작업 전 실제 스펙 조사**: 실제 함수명, 이벤트명, JSON 포맷, API 엔드포인트.

### 1-2. 레이아웃 전략 선택

| 패턴 | 적합 대상 | 구조 |
|------|-----------|------|
| Vertical Flow | 웹 아키텍처, 요청 흐름 | 상→하 레이어 |
| Horizontal Pipeline | CI/CD, ETL, 데이터 파이프라인 | 좌→우 단계 |
| Hub and Spoke | 이벤트 기반, 중앙 집중 시스템 | 중앙 노드 + 방사형 |
| Data Flow | 파라미터 흐름, 콜 체인 | 멀티 컬럼 + 주석 |

### 1-3. 시각 패턴 라이브러리

**Fan-Out** (1→多): 중앙에서 화살표 방사. 소스, PRD, 루트 원인.

**Convergence** (多→1): 여러 입력 → 단일 출력. 집계, 퍼널.

**Timeline**: 수직/수평 선 + 마커 도트(10-20px ellipse) + 자유 텍스트 레이블.

**Tree**: `line` 요소 + 자유 텍스트. 박스 없음.

**Spiral/Cycle**: 순환 화살표. 피드백 루프.

**Assembly Line**: Input → [PROCESS] → Output. 변환, 처리.

> **핵심**: 박스를 기본으로 쓰지 않는다. 자유 텍스트(free-floating)가 기본이고, 도형은 의미가 있을 때만 추가. 전체 텍스트 요소의 30% 미만만 컨테이너 안에.

---

## Phase 2: JSON 생성

### Python 스크립트 접근법 (30+ 요소 시 강력 권장)

복잡한 다이어그램은 JSON 직접 작성 대신 **Python 스크립트**로 생성한다.
`diagram_utils.py`를 import하면 좌표 계산, ID 관리, 텍스트 폭 계산이 자동화된다.

```python
import sys
import os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/fz-excalidraw/references"))
from diagram_utils import reset, rect, txt, arr, elbow_arrow, hstack, vstack, diamond, ln, code_box, save

reset()  # 버퍼 초기화

# 섹션 경계 명시 (Anti-Overlap 규칙 5)
SEC_A_X, SEC_A_W = 40, 460       # 섹션 A
SEC_B_X = SEC_A_X + SEC_A_W + 40 # 섹션 B 시작 (divider gap=40)
SEC_B_W = 500

# 노드 배치
nodes = hstack(["A", "B", "C"], x_start=SEC_A_X, y=100,
               item_w=140, item_h=50, gap=20,
               fill="#3b82f6", stroke="#1e3a5f", text_color="#ffffff")

# 화살표 (레이블 없음 — 별도 txt로)
a_eid, ax, ay = nodes[0]
b_eid, bx, by = nodes[1]
arr(ax, ay + 25, bx - 70, by + 25)                    # 수평 화살표
txt(ax + 10, ay - 20, 80, 14, "호출", fs=10, c="#64748b")  # 레이블은 위에

save("/tmp/output.excalidraw")
```

**캔버스 크기 가이드**:
- 섹션 1개: 폭 400-500px
- 섹션 3개 나란히: 폭 ≥ 1,600px (섹션 500 × 3 + divider 40 × 2)
- Evidence 블록 포함: 섹션당 추가 300-400px

**헬퍼 함수 목록**:
| 함수 | 용도 |
|------|------|
| `rect(x,y,w,h,fill,stroke,label)` | 사각형 + 텍스트 (multi-line `\\n` 지원) |
| `ellipse(x,y,w,h,fill,stroke,label)` | 원/타원 |
| `diamond(x,y,w,h,fill,stroke,label)` | 다이아몬드 (결정) |
| `txt(x,y,w,h,text,fs,c)` | 자유 텍스트 |
| `ln(x1,y1,x2,y2,c)` | 구조선 (비화살표) |
| `arr(x1,y1,x2,y2,c)` | 직선 화살표 (label 없음) |
| `elbow_arrow(x1,y1,x2,y2,turn_y)` | L자형 엘보우 화살표 |
| `hstack(labels,x,y,w,h,gap)` | 가로 스택 (gap≥20 강제) |
| `vstack(labels,x,y,w,h,gap)` | 세로 스택 (gap≥20 강제) |
| `code_box(x,y,w,lines,title)` | 코드/JSON 증거 박스 |
| `save(path)` | .excalidraw 파일 저장 |

---

### 도형 의미

| 개념 타입 | 도형 |
|-----------|------|
| 레이블, 설명 | **없음** (free-floating text) |
| 타임라인 마커 | small `ellipse` (10-20px) |
| 시작/트리거 | `ellipse` |
| 종료/결과 | `ellipse` |
| 결정/조건 | `diamond` |
| 프로세스/액션 | `rectangle` |
| 계층 노드 | lines + text (박스 없음) |

### 색상 규칙

- **반드시 `references/color-palette.md`에서 색상 선택**. 임의 색상 금지.
- semantic purpose → fill/stroke 쌍 사용.
- 자유 텍스트 계층: Title(`#1e40af`) > Subtitle(`#3b82f6`) > Detail(`#64748b`).

### JSON 구조

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "https://excalidraw.com",
  "elements": [],
  "appState": {
    "viewBackgroundColor": "#ffffff",
    "gridSize": 20
  },
  "files": {}
}
```

### 텍스트 필드 규칙

`text` / `originalText`에는 **읽기 가능한 단어만**. 설정값·ID 금지.

```json
{ "text": "Start", "originalText": "Start", "fontSize": 16, "fontFamily": 3 }
```

### 레이아웃 원칙

- **계층 스케일**: Hero 300×150 → Primary 180×90 → Secondary 120×60 → Small 60×40
- **여백 = 중요도**: 핵심 요소 주변 200px+ 여백
- **모든 관계는 화살표로**: 위치만으로 관계 표현 금지
- `roughness: 0`, `opacity: 100` (투명도 사용 금지)
- 90도 엘보우 화살표 권장, 곡선은 3+ points 배열로

---

### 레이아웃 충돌 방지 규칙 (Anti-Overlap) ⚠️

겹침의 3대 원인: **화살표 인라인 레이블 / 대각선 화살표 / 텍스트 폭 부족**

#### 규칙 1: 화살표 인라인 레이블 금지
화살표 `points` 중간에 레이블을 배치하지 않는다. 반드시 **별도 free-floating text**로 배치한다.

```python
# ❌ 금지: arr() 함수에 label 인자 사용
arr(x1, y1, x2, y2, label="someText")  # 화살표와 겹침 발생

# ✅ 올바른 방법: 화살표 옆 공백에 별도 txt() 배치
arr(x1, y1, x2, y2)
# 수직 화살표면 레이블을 오른쪽에
txt(max(x1,x2) + 6, (y1+y2)//2 - 8, 80, 16, "label", fs=10, c="#64748b")
# 수평 화살표면 레이블을 위쪽에
txt((x1+x2)//2 - 30, min(y1,y2) - 18, 60, 14, "label", fs=10, c="#64748b")
```

#### 규칙 2: 직교 화살표 전용 (대각선 금지)
모든 화살표는 수평(→) 또는 수직(↓) 또는 L자형 엘보우만 사용한다.

```python
# ❌ 금지: 대각선 화살표
arr(100, 100, 300, 250)  # 45도 대각선 → 경로상 요소와 겹침

# ✅ 수직 → 수직
arr(240, 200, 240, 260)  # 정수직

# ✅ L자형 엘보우 (line 두 개 조합)
ln(240, 200, 240, 230)   # 수직 부분
ln(240, 230, 400, 230)   # 수평 부분
arr(400, 230, 400, 260)  # 마지막 수직 부분
```

#### 규칙 3: 텍스트 폭 = 글자 수 기반 계산
텍스트 width를 임의로 정하지 말고 내용 길이 기반으로 계산한다.

```python
# 텍스트 폭 계산식
def text_width(text: str, font_size: int = 12) -> int:
    # 한글 1자 ≈ font_size * 0.9, 영문 1자 ≈ font_size * 0.55
    chars = len(text)
    return max(60, int(chars * font_size * 0.65))

# rect width도 내부 텍스트 길이에 맞춰 설정
label = "ContentDetailPlayer"
w = max(140, text_width(label, font_size=12) + 20)  # padding 20px
rect(x, y, w, 48, ...)
```

#### 규칙 4: 형제 노드 간 최소 간격
같은 레벨의 노드는 최소 20px gap을 확보한다.

```python
# ✅ 형제 노드 X 좌표 계산
node_w = 160
gap = 20
nodes = ["Header", "List", "Player", "WebView", "LiveDetail", "TvingTalk"]
for i, name in enumerate(nodes):
    x = start_x + i * (node_w + gap)
    rect(x, y, node_w, 48, ...)

# 레이어 간 수직 간격: 노드 height + 최소 60px
layer_gap = node_height + 60
next_y = current_y + layer_gap
```

#### 규칙 5: 섹션 경계 확인
멀티 섹션 다이어그램은 섹션마다 `x_end = x_start + 섹션_width`를 명시적으로 계산하고, 다음 섹션 `x_start = x_end + divider_gap(40px)`으로 시작한다.

```python
# ✅ 섹션 경계 명시
CA_X, CA_W = 40, 440        # Clean Architecture 섹션
DIV1_X = CA_X + CA_W + 20   # 462
FLOW_X, FLOW_W = DIV1_X + 20, 900   # Flow 섹션
DIV2_X = FLOW_X + FLOW_W + 20
CODE_X = DIV2_X + 20        # Code 섹션
```

---

## Phase 3: Render & Validate 루프 (필수)

JSON만으로 다이어그램을 판단할 수 없다. **생성 후 반드시 렌더링하여 눈으로 확인**한다.

### 렌더 명령

```bash
cd ~/.claude/skills/fz-excalidraw/references && uv run python render_excalidraw.py <path-to-file.excalidraw>
```

렌더 결과 PNG를 **Read 도구로 직접 열어서** 확인한다.

### 최초 설정 (render_excalidraw.py 없을 때)

```bash
cd ~/.claude/skills/fz-excalidraw/references
uv sync
uv run playwright install chromium
```

### 검증 루프

```
1. Render → PNG Read
2. 비전 확인: 설계한 레이아웃과 일치하는가?
3. 결함 확인: 텍스트 잘림 / 요소 겹침 / 화살표 오연결 / 불균형 간격
4. Fix → 재렌더 → 재확인
5. 반복 (보통 2-4회). 아래 완료 조건 충족 시 중단.
```

**완료 조건:**
- 렌더가 설계 의도와 일치
- 텍스트 잘림/겹침 없음
- 화살표가 정확한 요소에 연결
- 간격 일관성 + 구성 균형

### 렌더 없이 진행 시

렌더 환경이 없으면 `.excalidraw` 파일을 생성하고, 사용자에게 Excalidraw에서 열어 확인하도록 안내.

---

## Phase 4: Quality Checklist

### 개념 (Technical 다이어그램)

- [ ] 실제 스펙 조사 완료 (실제 함수명/이벤트명/포맷 사용)
- [ ] Evidence artifacts 포함 (코드 스니펫, JSON 예시, 실제 데이터)
- [ ] 다이어그램이 텍스트로 설명 불가한 것을 보여주는가
- [ ] 각 주요 개념이 다른 시각 패턴 사용

### 구조

- [ ] 자유 텍스트 우선 (컨테이너 30% 이하)
- [ ] 모든 관계에 화살표/선 존재
- [ ] 시각적 흐름 방향 명확

### 기술

- [ ] `text` 필드에 읽기 가능한 단어만
- [ ] `fontFamily: 3`
- [ ] `roughness: 0`, `opacity: 100`
- [ ] 색상 전부 `color-palette.md`에서 선택

### 시각 검증 (렌더 필수)

- [ ] 렌더링 후 눈으로 확인
- [ ] 텍스트 잘림/오버플로우 없음
- [ ] 요소 비의도적 겹침 없음
- [ ] **화살표 레이블이 노드/화살표와 겹치지 않음** ← 신규
- [ ] **대각선 화살표 없음** (수평/수직/L자형만) ← 신규
- [ ] **형제 노드 간 gap ≥ 20px** ← 신규
- [ ] 화살표가 정확한 요소에 연결
- [ ] 읽기 가능한 텍스트 크기

---

## 기존 파일 업데이트

기존 `.excalidraw` 파일 수정 시:
1. `Read` 도구로 파일 읽기
2. 기존 요소의 ID, 좌표, 바인딩 관계 파악
3. 필요한 요소만 추가/수정 (기존 구조 최대 유지)
4. 렌더 루프 적용

---

## 출력

- `.excalidraw` 파일 (사용자가 지정한 경로 또는 현재 작업 디렉토리)
- 렌더 PNG (렌더 환경 있을 때, `.excalidraw`와 같은 디렉토리)
- 완료 보고: 파일 경로 + 주요 레이아웃 결정 요약

---

## Few-shot 예시

```
BAD (대각선 화살표 + 겹침):
A ─────────> C
  \         ↑
   \       /
    B ────
→ 대각선 화살표, 텍스트 겹침, 간격 불규칙.

GOOD (수직/수평 + L자형):
A ──────── B
           │
           ▼
           C
→ 수평/수직만 사용, L자형 연결, 노드 간 gap ≥ 20px.
```

```
BAD (JSON 직접 작성):
요소 200개를 한 번에 JSON으로 생성
→ 좌표 충돌, 바인딩 오류, 렌더 후 수정 폭주.

GOOD (레이어별 점진 생성 + 렌더 루프):
Phase 2: 레이어 분리 → L1(노드) → L2(화살표+바인딩) → L3(레이블)
Phase 3: Write → 렌더 확인 → 좌표 조정 → 재렌더 (최대 3회)
```

## Boundaries

**Will**:
- Excalidraw JSON (.excalidraw) 파일 생성 및 수정
- 아키텍처, RIBs 구조, 데이터 흐름, 모듈 의존성 시각화
- 기존 다이어그램 요소 추가/수정/삭제

**Will Not**:
- Mermaid, PlantUML 등 Excalidraw 외 포맷 출력
- 코드 구현 (→ /fz-code)
- 텍스트 기반 다이어그램만 필요한 경우 (→ 직접 ASCII 출력)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| JSON 파싱 실패 | 기존 파일 백업 후 재생성 | 새 파일로 생성 |
| 렌더 확인 시 겹침 감지 | 좌표 재계산 + 재렌더 (최대 3회) | 사용자에게 수동 조정 안내 |
| 바인딩 ID 불일치 | 요소 ID 재매핑 | 바인딩 없이 화살표만 생성 |
| 파일 크기 초과 (>100KB) | 레이어 분리 제안 | 사용자 에스컬레이션 |
