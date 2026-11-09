#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 템플릿 · 본문만 읽는다.
"""check_pr_template.py — PR 본문이 템플릿의 섹션 구조를 그대로 따랐는지 대조한다(F-397).

왜: "템플릿을 참조했다" 와 "산출물이 템플릿 구조다" 는 다른 명제다. 템플릿을 읽고도 섹션을 지우거나 새 계층을 신설해
실행마다 본문 모양이 달라졌다(사용자: "왜 자꾸 … 할 때마다 다르게 올리는 거야"). 눈 대조 대신 섹션 제목을 diff 한다.

섹션: 템플릿에 ATX 제목(`#` …)이 있으면 ATX 제목, 없으면 구분선(`---` · `***` · `___`) 바로 앞 줄 — 본문도 같은 규칙으로 뽑는다.
      코드 펜스 안 · HTML 주석 안은 보지 않는다. 제목은 굵게 표시 · 끝 콜론 · 공백을 정규화해 비교한다(계층 깊이는 보지 않는다).
판정: 템플릿에만 있는 섹션(MISSING) · 본문에만 있는 섹션(EXTRA)은 실패다. 템플릿이 '해당 없으면 지우라' 고 한 섹션은
      `--allow-missing` 으로, 의도해 더한 섹션은 `--allow-extra` 로 이름을 댄다 — 의도된 차이만 통과한다.

사용: check_pr_template.py --template FILE --body FILE|- [--allow-missing 제목]... [--allow-extra 제목]... | --self-test
exit: 0 일치(허용한 차이만) · 1 섹션 차이 · 2 대조 불가(파일 없음 · 템플릿에서 섹션 0개 — ⛔ 통과 아님)
"""
import argparse
import collections
import os
import re
import sys
import tempfile

ATX = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
RULE = re.compile(r"^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
COMMENT = re.compile(r"<!--.*?-->", re.S)


def norm(title):
    t = re.sub(r"^#+\s*", "", title.strip())
    t = re.sub(r"\*\*|__", "", t)
    return re.sub(r"\s+", " ", t).strip().rstrip(":：").strip()


def _lines(text):
    out, fence = [], None
    for line in COMMENT.sub("", text).split("\n"):
        m = FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            out.append(line)
    return out


def sections(text, style=None):
    """(제목 목록, 쓴 규칙). style 이 없으면 고른다 — ATX 제목이 하나라도 있으면 'atx', 없으면 'rule'."""
    lines = _lines(text)
    atx = [norm(m.group(2)) for m in (ATX.match(ln) for ln in lines) if m]
    if style is None:
        style = "atx" if atx else "rule"
    if style == "atx":
        return [t for t in atx if t], style
    titles, prev = [], ""
    for ln in lines:
        if RULE.match(ln) and prev.strip():
            titles.append(norm(prev))
        prev = ln
    return [t for t in titles if t], style


def compare(template_text, body_text, allow_missing=(), allow_extra=()):
    tpl, style = sections(template_text)
    body, _ = sections(body_text, style)
    a, b = collections.Counter(tpl), collections.Counter(body)
    missing = list((a - b).elements())
    extra = list((b - a).elements())
    am, ae = {norm(x) for x in allow_missing}, {norm(x) for x in allow_extra}
    return {"style": style, "template": tpl, "body": body,
            "missing": [t for t in missing if t not in am], "extra": [t for t in extra if t not in ae],
            "allowed": [t for t in missing if t in am] + [t for t in extra if t in ae]}


def run(template, body, allow_missing=(), allow_extra=(), out=sys.stdout):
    try:
        with open(template, encoding="utf-8") as fh:
            tpl = fh.read()
        if body == "-":
            text = sys.stdin.read()
        else:
            with open(body, encoding="utf-8") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"UNRUN: 읽지 못했다 — {e} (⛔ 통과 아님)", file=out)
        return 2
    r = compare(tpl, text, allow_missing, allow_extra)
    if not r["template"]:
        print("UNRUN: 템플릿에서 섹션을 찾지 못했다(ATX 제목 · 구분선 앞 줄 0개) — 대조할 틀이 없다 (⛔ 통과 아님)", file=out)
        return 2
    for t in r["missing"]:
        print(f"MISSING {t} — 템플릿 섹션이 본문에 없다(지우라는 지시가 있는 섹션이면 --allow-missing)", file=out)
    for t in r["extra"]:
        print(f"EXTRA {t} — 템플릿에 없는 섹션을 신설했다(의도한 것이면 --allow-extra)", file=out)
    print(f"pr-template: style={r['style']} template={len(r['template'])} body={len(r['body'])} "
          f"missing={len(r['missing'])} extra={len(r['extra'])} allowed={len(r['allowed'])}", file=out)
    return 1 if r["missing"] or r["extra"] else 0


def self_test():
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    class Sink:
        def __init__(self):
            self.text = ""

        def write(self, s):
            self.text += s

    def check(name, cond, got):
        nonlocal passed
        if cond:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(name)
            print(f"FAIL {name}: {got}")

    tpl = ("<!-- 해당 사항이 없으면 섹션을 통째로 지운다 -->\n## 요약\n- \n\n## 변경 사항\n- \n\n## 관련 로그, 스크린샷\n| 전 | 후 |\n|---|---|\n\n"
           "## 확인 사항\n- [ ] 빌드\n")
    filled = ("## 요약\n- 진입 화면 버그 수정\n\n## 변경 사항\n- 상태 초기화 순서\n\n```bash\n# 주석은 제목이 아니다\n```\n\n"
              "## 관련 로그, 스크린샷\n| 전 | 후 |\n|---|---|\n\n## 확인 사항\n- [x] 빌드\n")
    dropped = filled.replace("## 관련 로그, 스크린샷\n| 전 | 후 |\n|---|---|\n\n", "")
    added = filled.replace("## 변경 사항\n", "## 변경 사항\n### 리뷰 포인트\n- 순서만 봐 주세요\n")
    rule_tpl = "**요약**\n---\n- \n\n**변경 사항**\n---\n- \n"
    with tempfile.TemporaryDirectory(prefix="fz-pr-template-") as d:
        def put(name, body):
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            return p

        t = put("tpl.md", tpl)

        def go(body, *allow, extra=()):
            s = Sink()
            return run(t, put("body.md", body), allow, extra, s), s.text

        rc, out = go(dropped)
        rc_ok, _ = go(dropped, "관련 로그, 스크린샷")
        check("f397-template-section-missing", rc == 1 and "MISSING 관련 로그, 스크린샷" in out and rc_ok == 0, f"{rc} {rc_ok} {out}")
        rc, out = go(added)
        rc_ok, _ = go(added, extra=("리뷰 포인트",))
        check("f397-template-section-extra", rc == 1 and "EXTRA 리뷰 포인트" in out and rc_ok == 0, f"{rc} {rc_ok} {out}")
        rc, out = go(filled)
        check("template-filled-matches", rc == 0 and "missing=0 extra=0" in out, out)
        rt = put("rule.md", rule_tpl)
        s = Sink()
        rc_rule = run(rt, put("rb.md", "**요약**\n---\n- 수정\n"), (), (), s)
        check("rule-style-sections", rc_rule == 1 and "MISSING 변경 사항" in s.text and "style=rule" in s.text, s.text)
        s1, s2 = Sink(), Sink()
        rc1 = run(os.path.join(d, "no-such.md"), put("b2.md", "x"), (), (), s1)
        rc2 = run(put("empty.md", "제목 없는 템플릿\n"), put("b3.md", "## 요약\n"), (), (), s2)
        check("unreadable-or-empty-template-unrun", rc1 == 2 and rc2 == 2 and "UNRUN" in s1.text + s2.text, f"{rc1} {rc2}")

    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--template", required=True)
    ap.add_argument("--body", required=True, help="본문 파일 · '-' 면 stdin")
    ap.add_argument("--allow-missing", action="append", default=[], metavar="제목")
    ap.add_argument("--allow-extra", action="append", default=[], metavar="제목")
    a = ap.parse_args(argv)
    return run(a.template, a.body, a.allow_missing, a.allow_extra)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
