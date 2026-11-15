# 개발과 릴리즈

fz 자체를 수정할 때의 절차.

```bash
# 소스코드 클론 (아래는 클론한 폴더를 /path/to/fz 로 적는다 — 각자의 경로로 바꾼다)
git clone https://github.com/jaewooongyun/fz.git /path/to/fz

# 로컬 개발 모드로 실행 (수정 즉시 반영)
claude --plugin-dir /path/to/fz

# alias 설정 (선택)
echo 'alias cfz="claude --plugin-dir /path/to/fz"' >> ~/.zshrc
```

## 릴리즈

절차는 루트 `CLAUDE.md` 의 `### 릴리즈 (변경사항 배포)` 절 한 곳에 둔다 — version bump(필수) · 발행 전 검사 · 출하 게이트 · 이번 판 태그 하나만 push · 발행 · 발행 뒤 검사를 그 절의 순서대로 따른다. 여기에 절차를 다시 적지 않는다(사본은 한쪽만 고쳐져 낡는다).

---
