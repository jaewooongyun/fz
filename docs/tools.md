# 함께 쓰는 도구

fz 가 번들하는 MCP 는 Serena 하나다. 나머지는 직접 등록한다. 빠진 도구가 있어도 fz 는 깨지지 않고 아래 표대로 대신한다.

## 도구별 설치

| 도구 | 없으면 | 설치 |
|------|--------|------|
| **Claude Code** | 동작 불가 | 네이티브 설치(권장) [설치 문서](https://code.claude.com/docs/en/setup) 또는 `npm install -g @anthropic-ai/claude-code` |
| **SuperClaude** | 리뷰 셋째 검증이 새 컨텍스트 에이전트로 · 설명 · 조사 명령은 건너뛴다 | `/plugin marketplace add SuperClaude-Org/SuperClaude_Plugin` 다음 `/plugin install sc@superclaude` |
| **Serena MCP** | 심볼 탐색이 Grep 으로 | 자동 등록. `uv` 가 필요하다(`brew install uv`). 첫 기동 전에 캐시를 채운다(아래) |
| **GPT CLI** (`@openai/codex`) | `[GPT 미사용 — CLI 없음]` 표기만 남는다. 켠 GPT 호출이 실패하면 교차 검증이 새 컨텍스트 Claude 검증자로 — 동종 검증 `[fresh-context: claude]` | `npm install -g @openai/codex` 뒤 CLI 로그인 1회 |
| **sequential-thinking** | 없으면 같은 분해를 표로 직접 쓴다 | `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Context7 MCP** | 라이브러리 문서가 WebSearch 로 | `claude plugin install context7@claude-plugins-official` |
| **pr-review-toolkit** | fz-review Phase 5 의 병렬 4 · 5 를 건너뛰고 보고에 한 줄 알린다 | 공식 마켓플레이스에서 `/plugin` 으로 설치 |

GitHub 는 MCP 서버 없이 `gh` CLI 로 다룬다. 조회 명령만 사전 승인하고 PR 생성과 리뷰 게시는 권한을 묻는다. 티켓 트래커는 프로젝트 `CLAUDE.md` 에 선언한 트래커 MCP 가 연결돼 있으면 그 도구로, 없으면 수동 입력으로 다룬다.

## 설치 뒤 확인

- ⛔ MCP 서버는 위 표의 이름 그대로 등록한다. 다른 이름이나 공식 마켓플레이스 플러그인으로 깔면 도구 이름이 `mcp__plugin_…` 으로 바뀌어 워커 에이전트에 오류 없이 전달되지 않는다. Context7 은 두 이름을 모두 받으므로 어느 쪽으로 깔아도 되고, 트래커 MCP 는 이름을 따지지 않는다
- ⛔ Serena 는 첫 기동에 약 300MB 를 받느라 MCP 연결 한도(30초)를 넘기기 쉽다. 한 번 실패하면 Claude Code 가 약 15분 동안 다시 띄우지 않으니 설치 직후 미리 받아 둔다
  ```bash
  uvx --from git+https://github.com/oraios/serena@v2.1.0 serena --help
  ```
- GPT CLI 는 설치만 하면 감지된다. 로그인하지 않았으면 GPT 단계를 건너뛰고 `[GPT 미사용 — 로그인 필요]` 를 남긴다
- 선택 도구를 쓰는 스킬은 첫 단계에 Serena 상태 뒤에 꼬리 ` · context7 목록✓|목록✗ · sc 목록✓|목록✗ · seq 목록✓|목록✗ · pr-review 목록✓|목록✗ · 스택 스킬 <이름, …>|없음` 로 도구 상태를 알린다(형식 `modules/tool-status.md`). 이 표시는 도구 목록에 이름이 있는지만 보므로 연결 여부는 `/mcp` 에서 `plugin:fz:serena` 가 connected 인지로 확인한다
