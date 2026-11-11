#!/usr/bin/env python3
# diff-parse: not-a-diff — `startswith("-")` 는 `time` 뒤 단어가 옵션 토큰(-p)인지 가르는 데만 쓴다. diff 를 파싱하지 않는다
"""공용 셸 · JS 템플릿 토크나이저 — fz-guard · gate_stop_hook · check_comment_worthy 가 같은 함수를 부른다(F-458).

허용 목록이다. RULES 표에 있는 꼴만 읽고, 표 밖 꼴은 전부 Unknown 을 돌려준다. 소비자는 Unknown 을 자기 쪽 보수
판정(쓰기 대상 미상 · GPT 호출 아님 · 미지 심볼)으로 바꾼다.
⛔ 읽기에 실패했을 때 정규식으로 되돌아가는 분기를 두지 않는다. 예전 근사기는 차단 목록이라 라운드마다 새 꼴이 샜다(F-458).

여기서는 낱말 · 연산자 · 리다이렉트 · 치환 경계만 가른다. 루프 · cd · source · 판정기 호출 같은 뜻은 소비자가 정한다.
⛔ mods/fz-guard/hooks/shell_tokens.py 와 바이트까지 같아야 한다 — 설치본은 하위 플러그인 폴더만 복사된다(health-check 가 cmp 로 잰다).

사용: shell_tokens.py --list-rules | --self-test
"""
from __future__ import annotations

import os
import re
import sys
from collections import namedtuple

# 허용 규칙 — 한 줄에 하나다. 개별 제거 probe(guides/harness-engineering.md §5.6)가 줄 단위로 지운다. 규칙을 지우면 그 꼴은 Unknown 이 된다
RULES = {
    "word": "plain unquoted word characters; NAME= NAME+= NAME[...]= at a word start assign (a subscript split by a blank, a word glued to ( other than a function definition, {fd} before a redirection and the reserved words case, coproc and function are outside)",
    "function-definition": "NAME () or NAME() at command position, then blanks or newlines, then a { ... } body (} closes only at command position) or a ( ... ) body, lexed recursively and returned as Func — the body is defined, not run (the function keyword form is outside)",
    "single-quote": "'...' with no escapes inside",
    "double-quote": '"..." where a backslash escapes only \\ " $ ` and newline',
    "ansi-c-quote": "$'...' with only the escapes \\n \\t \\r \\\\ \\' \\\" \\a \\b \\e \\f \\v (octal, hex and unicode escapes are outside)",
    "backslash-escape": "\\X outside quotes is the literal X; \\<newline> joins lines only right after a blank (never inside a word or after an operator)",
    "parameter": "$NAME, $1, $?, and ${...} with no brace, quote, parenthesis or substitution inside ($[...] is outside)",
    "command-substitution": "$( ... ) lexed recursively, also inside double quotes and unquoted heredoc bodies",
    "backtick-substitution": "` ... ` lexed recursively; a backslash anywhere inside is outside",
    "arith-expansion": "$(( ... )) with balanced parentheses and no substitution inside",
    "process-substitution": "<( ... ) and >( ... ) starting a word (not glued to a previous word), lexed recursively",
    "operator": "; ;; & && || | |& ( ) and newline (;;& and ;& are outside)",
    "redirection": "[n]> [n]>> [n]>| [n]< [n]<> &> &>> [n]>& [n]<& <<< followed by a target word that is not a comment",
    "heredoc": "<<[-]DELIM with a plain delimiter, whose body ends at a DELIM line (no line continuation in an unquoted body; a heredoc still open at the end of a whole command or a substitution is outside)",
    "comment": "# at a word start runs to the end of the line",
    "test-command": "[[ ... ]] at command position: < > ( ) && || ! inside are words; a =~ regex operand and <( >( inside are outside",
    "arith-command": "(( ... )) at command position with balanced parentheses and no substitution inside ((( elsewhere, as in an arithmetic for, is outside)",
    "js-template": "JS `...${expr}...` where expr nests braces, strings, templates and comments ending at CR LF U+2028 U+2029; / after an identifier, number, ] or closing quote is division, any other / (regex literal, or after a closing parenthesis) and HTML-like comments are outside",
}

Word = namedtuple("Word", "text start end quoted expands subs assign")   # text = 따옴표를 벗긴 값(`$X` 는 글자 그대로) · subs = 치환별 토큰 목록 · assign = 따옴표 밖 NAME= 로 시작
Op = namedtuple("Op", "text start end")
Redir = namedtuple("Redir", "op fd target start end heredoc")          # heredoc = {"body", "quoted", "subs"} | None
Func = namedtuple("Func", "name body start end")                       # 함수 정의 — body = 본문 토큰 목록(정의만 되고 지금 실행되지 않는다)
_FUNC_HEAD = re.compile(r"[ \t]*\([ \t]*\)")
_FUNC_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_OPS = ("&&", "||", ";;", "|&", ";", "&", "|", "(", ")", "\n")
_REDIR = re.compile(r"()(&>>|&>)|([0-9]*)(>>|>\||>&|<&|<<<|<<-|<<|<>|>|<)")   # `&>` 앞 숫자는 fd 가 아니라 단어다(`2&>f` 의 2)
_ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=")   # NAME= · NAME+= · NAME[i]= — 앞 대입을 명령으로 읽지 않는다
_META = frozenset(" \t\n;&|()<>")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9?$!@*#-]")
_CMD_WORDS = frozenset(("!", "{", "if", "then", "else", "elif", "do", "while", "until", "time"))   # 뒤가 아직 명령 자리인 예약어
_ANSI = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "v": "\v"}


class Unknown:
    """표 밖 꼴 — 소비자는 이것을 통과로 읽지 않는다. `why` 는 진단용 사유, `pos` 는 원문 위치다."""
    __slots__ = ("why", "pos")

    def __init__(self, why, pos):
        self.why, self.pos = why, pos

    def __repr__(self):
        return f"UNKNOWN({self.why}@{self.pos})"


def is_unknown(x) -> bool:
    return isinstance(x, Unknown)


class _Giveup(Exception):
    def __init__(self, why, pos):
        super().__init__(why)
        self.why, self.pos = why, pos


def _bracket_depth(t):
    """`[` 로 시작하는 글자의 괄호 깊이 — 첫 `[` 가 닫히면 0(첨자가 이 단어 안에서 끝났다)."""
    depth = 0
    for ch in t:
        depth += {"[": 1, "]": -1}.get(ch, 0)
        if depth == 0:
            return 0
    return depth


class _Lexer:
    def __init__(self, s, i=0, fragment=False):
        self.s, self.n, self.i = s, len(s), i
        self.fragment = fragment   # segments() 가 나눈 조각 — heredoc 본문이 다른 조각에 있다
        self.pending = []          # 이 줄의 heredoc — 다음 줄부터 본문
        self.quoted = []           # 맨 바깥 따옴표 · 이스케이프 구간 (시작, 끝) — 치환 안은 코드라 넣지 않는다

    def need(self, rule):
        if rule not in RULES:
            raise _Giveup("rule-off:" + rule, self.i)

    def blank(self, newline=False):
        s = self.s
        while self.i < self.n:
            if s[self.i] in " \t" or (newline and s[self.i] == "\n"):
                self.i += 1
            elif s.startswith("\\\n", self.i):
                self.need("backslash-escape")
                if self.i and s[self.i - 1] not in " \t\n":
                    raise _Giveup("continuation-after-nonblank", self.i)   # `&\<줄>&` 는 `&&` · `X\<줄>=1` 은 대입이다 — 이어 붙이면 경계가 바뀐다
                self.i += 2
            else:
                break

    def run(self, closer=False):
        s, toks, depth, cmd_pos, test, after_time, brace = self.s, [], 0, True, False, False, 0   # closer: True = `)` · "}" = 함수 본문
        while True:
            self.blank(test)
            if self.i >= self.n:
                if closer:
                    raise _Giveup("unterminated-substitution" if closer is True else "unterminated-function-body", self.i)
                if test:
                    raise _Giveup("unterminated-test", self.i)
                if self.pending and not self.fragment:
                    raise _Giveup("heredoc-open-at-end", self.i)   # 전체 명령인데 본문 줄이 없다
                for hd in self.pending:          # 표지 줄에서 끝난 조각(본문은 다른 조각) — 본문 없음
                    hd.update(body="", subs=())
                return toks
            c = s[self.i]
            if c == "#":
                self.need("comment")
                k = s.find("\n", self.i)
                self.i = self.n if k < 0 else k
                continue
            if test:
                if c in "<>" and s.startswith("(", self.i + 1):
                    raise _Giveup("procsub-in-test", self.i)   # 시험 안의 <( 는 실행되는 치환이다 — 낱말로 읽으면 경계를 잃는다
                if c in "<>()!&|;":
                    t = s[self.i:self.i + 2] if s.startswith(("&&", "||"), self.i) else c
                    if t in (";", "&", "|"):
                        raise _Giveup("operator-inside-test", self.i)
                    toks.append(Word(t, self.i, self.i + len(t), False, False, (), False))
                    self.i += len(t)
                    continue
                w = self.word()
                if w.text == "=~" and not w.quoted:
                    raise _Giveup("test-regex", w.start)   # 정규식 피연산자의 ( ) | 는 단어 경계가 아니다
                toks.append(w)
                if w.text == "]]" and not w.quoted:
                    test, cmd_pos = False, False
                continue
            if s.startswith("((", self.i) and not cmd_pos:
                raise _Giveup("arith-for", self.i)   # `for ((i=0;i<3;i++))` 의 < 는 리다이렉트가 아니다
            if cmd_pos and s.startswith("((", self.i):
                self.need("arith-command")
                end = self.arith(self.i + 2)
                toks.append(Word(s[self.i:end], self.i, end, False, True, (), False))
                self.i, cmd_pos = end, False
                continue
            if c in "<>" and s.startswith("(", self.i + 1):
                toks.append(self.word())
                cmd_pos = False
                continue
            m = _REDIR.match(s, self.i)
            if m:
                toks.append(self.redirect(m))
                continue
            if s.startswith((";;&", ";&"), self.i):
                raise _Giveup("case-fallthrough", self.i)   # bash 는 연산자 하나로 읽는다
            op = next((o for o in _OPS if s.startswith(o, self.i)), None)
            if op:
                self.need("operator")
                start = self.i
                self.i += len(op)
                if op == ")":
                    if closer is True and depth == 0:
                        if self.pending:
                            raise _Giveup("heredoc-open-in-substitution", start)   # `$(cat <<EOF)` — 본문이 치환 밖 줄에 있다
                        return toks
                    if closer == "}" and depth == 0:
                        raise _Giveup("function-body-paren", start)   # 짝 없는 ) — 본문 경계를 모른다
                    depth -= 1
                elif op == "(":
                    depth += 1
                elif op == "\n" and self.pending:
                    self.heredocs()
                toks.append(Op(op, start, self.i))     # 줄바꿈의 끝 = heredoc 본문 뒤 — 조각에 본문이 들지 않는다
                cmd_pos = op != ")"
                continue
            w = self.word()
            if closer == "}" and cmd_pos and not w.quoted and w.text == "}" and brace == 0:
                if self.pending:
                    raise _Giveup("heredoc-open-in-function", w.start)
                return toks                      # 함수 본문 끝 — `}` 는 명령 자리에서만 예약어다
            if cmd_pos and w.text == "case" and not w.quoted:
                raise _Giveup("case", w.start)   # 패턴의 `|` · `)` 는 파이프 · 닫는 괄호가 아니다(치환 안에서는 치환 끝과도 섞인다)
            if cmd_pos and w.text in ("coproc", "function") and not w.quoted:
                raise _Giveup(w.text, w.start)   # coproc 뒤 단어는 이름 · 명령이 문법으로 갈리고 function 꼴은 표 밖이다
            if cmd_pos and not w.quoted and _FUNC_HEAD.match(s, self.i):
                toks.append(self.funcdef(w))     # 본문은 정의만 되고 실행되지 않는다 — 명령 자리 토큰으로 읽지 않는다
                cmd_pos = False
                continue
            if s.startswith("()", self.i):
                raise _Giveup("function-definition", self.i)   # 명령 자리 밖 · 따옴표 든 이름 뒤의 () — 표 밖이다
            toks.append(w)
            if cmd_pos and not w.quoted and w.text in ("{", "}"):
                brace += 1 if w.text == "{" else -1   # 함수 본문 안 `{ …; }` 묶음 — 그 `}` 는 본문을 닫지 않는다
            if cmd_pos and w.text == "[[" and not w.quoted:
                self.need("test-command")
                test = True
                continue
            keep = after_time and w.text.startswith("-") and not w.quoted      # `time -p` 뒤는 아직 명령 자리다
            after_time = cmd_pos and not w.quoted and (w.text == "time" or (after_time and keep))
            cmd_pos = cmd_pos and not w.quoted and (w.text in _CMD_WORDS or keep)

    def redirect(self, m):
        self.need("redirection")
        start = self.i
        fd, op = (m.group(1), m.group(2)) if m.group(2) else (m.group(3), m.group(4))
        self.i = m.end()
        if op in ("<<", "<<-"):
            self.need("heredoc")
        self.blank()
        s = self.s
        if self.i >= self.n or s[self.i] == "#" or (s[self.i] in _META and not (s[self.i] in "<>" and s.startswith("(", self.i + 1))):
            raise _Giveup("redirection-without-target", self.i)   # `> #x` 의 # 은 주석이다 — 대상이 없다
        t = self.word()
        hd = None
        if op in ("<<", "<<-"):
            if t.subs or t.expands:
                raise _Giveup("heredoc-delimiter-complex", t.start)   # 표지는 확장하지 않는다 — 치환을 코드로 적지 않는다
            hd = {"delim": t.text, "quoted": t.quoted, "strip": op == "<<-", "body": None, "subs": ()}
            self.pending.append(hd)
        return Redir(op, fd, t, start, self.i, hd)

    def heredocs(self):
        s, n = self.s, self.n
        for hd in self.pending:
            j, lines = self.i, []
            while True:
                if j >= n:
                    raise _Giveup("heredoc-unterminated", self.i)
                k = s.find("\n", j)
                k = n if k < 0 else k
                line = s[j:k]
                if (line.lstrip("\t") if hd["strip"] else line) == hd["delim"]:
                    j = min(k + 1, n)
                    break
                if not hd["quoted"] and line.endswith("\\"):
                    raise _Giveup("heredoc-continuation", j)   # 따옴표 없는 본문은 줄 연속을 먼저 잇고 표지를 본다
                lines.append(line)
                j = k + 1
            hd["body"] = "\n".join(lines)
            if not hd["quoted"]:                       # 따옴표 없는 표지 — 본문의 $( ) · 백틱은 실행된다
                sub, subs = _Lexer(hd["body"]), []
                sub.dq([], subs, close=None)
                hd["subs"] = tuple(subs)
            self.i = j
        self.pending = []

    def word(self):
        s, n, start = self.s, self.n, self.i
        text, subs, quoted, expands = [], [], False, False
        while self.i < n:
            c = s[self.i]
            if c in "<>" and self.i == start and s.startswith("(", self.i + 1):
                self.need("process-substitution")
                toks, end = self.sub(self.i + 2)
                subs.append(toks)
                text.append(s[self.i:end])
                self.i, expands = end, True
                continue
            if c in _META:
                if c in "<>" and s.startswith("(", self.i + 1):
                    raise _Giveup("process-substitution-glued", self.i)   # `x<(…)` 는 한 단어다
                break
            if c == "'":
                self.need("single-quote")
                k = s.find("'", self.i + 1)
                if k < 0:
                    raise _Giveup("unterminated-single-quote", self.i)
                text.append(s[self.i + 1:k])
                self.quoted.append((self.i, k + 1))
                self.i, quoted = k + 1, True
            elif c == '"':
                self.need("double-quote")
                expands |= self.dq(text, subs)
                quoted = True
            elif c == "\\":
                self.need("backslash-escape")
                nx = s[self.i + 1:self.i + 2]
                if not nx:
                    raise _Giveup("trailing-backslash", self.i)
                if nx == "\n":
                    raise _Giveup("continuation-inside-word", self.i)   # 이어 붙인 단어의 대입 · fd 접두 판정이 원문과 갈린다
                after = s[self.i + 2:self.i + 3]
                if nx in "<>|&;()" and after and after in "<>|&;":
                    raise _Giveup("escape-before-operator", self.i)   # `\>>` · `\>>>` — 사람이 잘못 읽는 꼴(GPT validate ISSUE-202623)
                text.append(nx)
                self.quoted.append((self.i, self.i + 2))
                self.i, quoted = self.i + 2, True
            elif c == "$":
                e, q = self.dollar(text, subs, in_dq=False)
                expands, quoted = expands or e, quoted or q
            elif c == "`":
                self.backtick(text, subs)
                expands = True
            else:
                self.need("word")
                text.append(c)
                self.i += 1
        if self.i == start:
            raise _Giveup("empty-word", self.i)
        if self.i < n and s[self.i] == "(" and "".join(text).endswith("=") and not quoted:
            raise _Giveup("array-assignment", self.i)
        if self.i < n and s[self.i] == "(" and not s.startswith("()", self.i):
            raise _Giveup("word-glued-paren", self.i)   # extglob `!(x)` · `*(a|b)` 는 한 단어다
        raw = s[start:self.i]
        if self.i < n and s[self.i] in "<>" and re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", raw):
            raise _Giveup("named-fd", start)   # `{fd}>f` 는 단어가 아니라 리다이렉트의 일부다
        sub = re.match(r"[A-Za-z_][A-Za-z0-9_]*\[", raw)
        if sub and _bracket_depth(raw[sub.end() - 1:]) != 0:
            raise _Giveup("subscript-split", self.i)   # `A[a b]=x` · `A[b[0] + 1]=x` 는 bash 가 대입 한 단어로 읽는다
        return Word("".join(text), start, self.i, quoted, expands, tuple(subs), bool(_ASSIGN.match(s, start)))

    def dq(self, text, subs, close='"'):
        """큰따옴표(close=None 이면 따옴표 없는 heredoc 본문) — 역슬래시는 \\ $ ` 줄바꿈(과 큰따옴표 안의 ") 만 이스케이프한다.
        $( ) · 백틱은 코드라 따옴표 구간에서 뺀다. 반환: 확장이 있는가."""
        s, n = self.s, self.n
        span = self.i
        if close:
            self.i += 1
        esc, expands = "\\$`\n" + (close or ""), False
        while True:
            if self.i >= n:
                if close:
                    raise _Giveup("unterminated-double-quote", span)
                break
            c = s[self.i]
            if close and c == close:
                self.i += 1
                break
            if c == "\\":
                nx = s[self.i + 1:self.i + 2]
                if nx and nx in esc:
                    if nx != "\n":
                        text.append(nx)
                    self.i += 2
                else:
                    text.append(c)
                    self.i += 1
                continue
            if c == "$" or c == "`":
                at = self.i
                if c == "`":
                    self.backtick(text, subs)
                    e = True
                else:
                    e = self.dollar(text, subs, in_dq=True)[0]
                expands |= e
                if s[at:at + 2] == "$(" or c == "`":   # 치환 — 따옴표 구간을 끊는다
                    self.quoted.append((span, at))
                    span = self.i
                continue
            text.append(c)
            self.i += 1
        if close:
            self.quoted.append((span, self.i))
        return expands

    def dollar(self, text, subs, in_dq):
        """`$` 로 시작하는 꼴 — 반환 (확장인가, 따옴표인가)."""
        s, i = self.s, self.i
        nx = s[i + 1:i + 2]
        if s.startswith("$((", i):
            self.need("arith-expansion")
            end = self.arith(i + 3)
        elif nx == "(":
            self.need("command-substitution")
            toks, end = self.sub(i + 2)
            subs.append(toks)
        elif nx == "{":
            self.need("parameter")
            end = self.brace(i + 2)
        elif nx == "'" and not in_dq:
            self.need("ansi-c-quote")
            j, out = i + 2, []
            while True:
                if j >= self.n:
                    raise _Giveup("unterminated-ansi-c-quote", i)
                if s[j] == "'":
                    break
                if s[j] == "\\" and j + 1 < self.n:
                    if s[j + 1] not in _ANSI:
                        raise _Giveup("ansi-c-escape", j)   # 8진 · 16진 · 유니코드 · \c 는 표 밖(`\056` 은 `.` 이다)
                    out.append(_ANSI[s[j + 1]])
                    j += 2
                    continue
                out.append(s[j])
                j += 1
            text.append("".join(out))
            self.quoted.append((i, j + 1))
            self.i = j + 1
            return False, True
        elif nx == '"' and not in_dq:
            raise _Giveup("locale-quote", i)
        elif nx == "[":
            raise _Giveup("legacy-arith", i)   # `$[1 + 2]` 는 한 단어다
        else:
            m = _NAME.match(s, i + 1)
            if not m:
                text.append("$")                   # 홀로 선 `$` 는 글자다
                self.i += 1
                return False, False
            self.need("parameter")
            end = m.end()
        text.append(s[i:end])
        self.i = end
        return True, False

    def brace(self, j):
        s, depth = self.s, 1
        while j < self.n:
            c = s[j]
            if c in "'\"`{(":
                raise _Giveup("parameter-complex", j)   # 첫 } 에서 닫는다 · 안쪽 ( 는 $( <( >( 치환이다 — 경계를 잘못 센다
            if c == "\\":
                j += 2
                continue
            depth += {"{": 1, "}": -1}.get(c, 0)
            j += 1
            if depth == 0:
                return j
        raise _Giveup("unterminated-parameter", j)

    def arith(self, j):
        s, depth = self.s, 0
        while j < self.n:
            c = s[j]
            if s.startswith("$(", j) and not s.startswith("$((", j) or c == "`":
                raise _Giveup("arith-substitution", j)
            if c == "(":
                depth += 1
            elif c == ")":
                if depth == 0:
                    if s.startswith("))", j):
                        return j + 2
                    raise _Giveup("arith-unbalanced", j)
                depth -= 1
            j += 1
        raise _Giveup("unterminated-arith", j)

    def sub(self, j):
        inner = _Lexer(self.s, j)
        toks = inner.run(closer=True)
        return toks, inner.i

    def funcdef(self, w):
        """`NAME ()` 뒤 본문 — `{ … }` · `( … )` 를 재귀로 읽어 Func 로 낸다(빈칸 · 줄바꿈 뒤 본문 허용)."""
        self.need("function-definition")
        s = self.s
        if w.expands or w.assign or not _FUNC_NAME.fullmatch(w.text):
            raise _Giveup("function-name", w.start)
        j = _FUNC_HEAD.match(s, self.i).end()
        while j < self.n and s[j] in " \t\n":
            if s[j] == "\n" and self.pending:
                raise _Giveup("heredoc-before-function-body", j)
            j += 1
        if s.startswith("{", j) and s[j + 1:j + 2] in (" ", "\t", "\n"):
            inner = _Lexer(s, j + 1)
            body = inner.run(closer="}")
        elif s.startswith("(", j):
            inner = _Lexer(s, j + 1)
            body = inner.run(closer=True)
        else:
            raise _Giveup("function-body-form", j)
        self.i = inner.i
        return Func(w.text, tuple(body), w.start, self.i)

    def backtick(self, text, subs):
        self.need("backtick-substitution")
        s, i = self.s, self.i
        j, buf = i + 1, []
        while True:
            if j >= self.n:
                raise _Giveup("unterminated-backtick", i)
            c = s[j]
            if c == "\\":
                raise _Giveup("backtick-backslash", j)   # 백틱 안 역슬래시는 바깥 따옴표 문맥에 따라 벗겨진다(\" \` \$ \\)
            if c == "`":
                break
            buf.append(c)
            j += 1
        subs.append(_Lexer("".join(buf)).run())   # 백틱 안 위치는 그 안 글자 기준이다
        text.append(s[i:j + 1])
        self.i = j + 1


def _lexer(src, fragment=False):
    lx = _Lexer(src, fragment=fragment)
    try:
        return lx, lx.run()
    except _Giveup as g:
        return lx, Unknown(g.why, g.pos)
    except RecursionError:
        return lx, Unknown("too-deep", 0)


def lex(src, fragment=False):
    """맨 바깥 토큰 목록(Word · Op · Redir) — 표 밖 꼴이면 Unknown. fragment = segments() 조각(열린 heredoc 의 본문은 다른 조각)."""
    if not isinstance(src, str):
        return Unknown("not-text", 0)
    return _lexer(src, fragment)[1]


def words(src, fragment=False):
    """맨 바깥 단어 글자 — 연산자 · 리다이렉트와 그 대상 · 주석은 빠진다. 못 읽으면 Unknown."""
    toks = lex(src, fragment)
    return toks if is_unknown(toks) else [t.text for t in toks if isinstance(t, Word)]


def segments(src):
    """맨 바깥 연산자(줄바꿈 ; ;; & && || | |&)로 나눈 원문 조각 — 따옴표 · 치환 안에서는 나누지 않고 heredoc 본문은 조각에 들지 않는다."""
    toks = lex(src)
    if is_unknown(toks):
        return toks
    out, start = [], 0
    for t in toks:
        if isinstance(t, Op) and t.text not in ("(", ")"):
            out.append(src[start:t.start])
            start = t.end
    out.append(src[start:])
    return out


def in_quotes(src, pos, fragment=False):
    """`src[pos]` 가 맨 바깥 따옴표 · 이스케이프 구간 안인가 — 치환 안은 실행되는 코드라 따옴표 밖이다. 못 읽으면 Unknown."""
    lx, toks = _lexer(src, fragment) if isinstance(src, str) else (None, Unknown("not-text", 0))
    if is_unknown(toks):
        return toks
    return any(a <= pos < b for a, b in lx.quoted)


def nested(t):
    """토큰 하나의 (단어 목록, 치환 토큰 목록들) — 리다이렉트는 대상 단어 · heredoc 본문 치환까지 · 함수 정의는 본문(깊이+1).
    ⛔ 함수 본문은 정의만 되고 지금 실행되지 않는다 — 실행 증거(GPT 호출)를 세는 소비자는 Func 를 따로 건너뛴다."""
    if isinstance(t, Func):
        return [], [list(t.body)]
    ws = [t] if isinstance(t, Word) else [t.target] if isinstance(t, Redir) else []
    subs = [sub for w in ws for sub in w.subs]
    if isinstance(t, Redir) and t.heredoc:
        subs += list(t.heredoc.get("subs") or ())
    return ws, subs


def all_words(src):
    """모든 깊이의 단어 (글자, 깊이) — 치환 · 리다이렉트 대상 · 따옴표 없는 heredoc 본문의 치환까지. 못 읽으면 Unknown."""
    toks = lex(src)
    if is_unknown(toks):
        return toks
    out = []

    def walk(ts, d):
        for t in ts:
            ws, subs = nested(t)
            out.extend((w.text, d) for w in ws)
            for sub in subs:
                walk(sub, d + 1)
    walk(toks, 0)
    return out


def simple_commands(toks, depth=0):
    """(단어 목록, 리다이렉트 목록, 깊이) — 연산자 사이 단순 명령마다. 치환 안의 명령은 깊이+1 로 뒤에 낸다."""
    cur_w, cur_r = [], []
    for t in toks:
        if isinstance(t, Op):
            if cur_w or cur_r:
                yield cur_w, cur_r, depth
            cur_w, cur_r = [], []
        elif isinstance(t, Word):
            cur_w.append(t)
        elif isinstance(t, Redir):
            cur_r.append(t)                      # 함수 정의(Func)는 이 깊이의 명령이 아니다 — 본문은 아래 nested 로 깊이+1
    if cur_w or cur_r:
        yield cur_w, cur_r, depth
    for t in toks:
        for sub in nested(t)[1]:
            yield from simple_commands(sub, depth + 1)


# 명령 자리 — 단순 명령 하나에서 실행되는 단어를 정한다. 쓰기인지 · 판정기 호출인지 같은 뜻은 소비자가 정한다
Cmd = namedtuple("Cmd", "name args redirs depth deferred unsure via")
# name = 실행되는 명령 단어(Word) | None(대입만 · 예약어 · 루프 머리 · 닫는 말 · 리다이렉트만) · args = 이름 뒤 단어 · redirs = 이 명령의 리다이렉트
# depth = 치환 깊이(함수 본문 +1) · deferred = 함수 정의 본문 · 함수에 붙은 리다이렉트(정의만 되고 지금 실행되지 않는다)
# unsure = 명령 자리를 못 정한 사유('' = 정함) · via = 거쳐 온 래퍼 이름(바깥부터)
_LEAD = frozenset(("!", "{", "if", "then", "else", "elif", "do", "while", "until"))   # 명령 자리에서만 예약어 — 뒤가 아직 명령 자리다
_CLOSE = frozenset(("}", "fi", "done", "esac"))
_HEAD = frozenset(("for", "select"))                   # `for NAME [in 단어…]` — 머리는 아무것도 실행하지 않는다(단어 안 치환은 깊이+1)
# 래퍼 — 이름: (값 없는 옵션, 값을 받는 옵션, 뒤를 실행하지 않는 옵션, 뒤 NAME=값 을 받는가). 표 밖 옵션이면 명령 자리를 모른다
WRAPPERS = {
    "env": ({"-i", "-", "--ignore-environment", "--"}, {"-u", "--unset", "-C", "--chdir"}, set(), True),   # -C 는 폴더를 옮긴다(소비자가 센다)
    "time": ({"-p", "-l", "-h", "--"}, set(), set(), True),      # 예약어 time · /usr/bin/time
    "nohup": ({"--"}, set(), set(), False),
    "command": ({"-p", "--"}, set(), {"-v", "-V"}, False),
    "exec": ({"-c", "-l", "--"}, {"-a"}, set(), False),
    "sudo": ({"-E", "-H", "-n", "--"}, {"-u", "-g"}, set(), False),
    "nice": ({"--"}, {"-n"}, set(), False),
    "caffeinate": ({"-d", "-i", "-m", "-s", "-u", "--"}, {"-t", "-w"}, set(), False),
    "xargs": ({"-0", "-r", "-t", "-x", "-o", "--"}, {"-n", "-I", "-L", "-P", "-d", "-E", "-s", "-J"}, set(), False),
}
SHELL_WRAPPERS = {   # commands(shells=True) 에서만 — `bash 스크립트 인자` 의 명령을 스크립트로 본다(실행 증거를 세는 소비자)
    "bash": ({"-e", "-x", "-u", "-l", "--norc", "--noprofile", "+e", "+x", "--"}, {"-o", "+o"}, {"-n"}, False),
    "sh": ({"-e", "-x", "-u", "--"}, {"-o"}, {"-n"}, False),
    "zsh": ({"-e", "-x", "-u", "-f", "--"}, {"-o"}, {"-n"}, False),
}


def _opt_kind(spec, w) -> str:
    """래퍼 뒤 단어의 종류 — 'flag' · 'takes'(다음 단어가 값) · 'noexec' · 'other'(표 밖 옵션) · ''(옵션 아님)."""
    t = w.text
    if w.quoted or not t.startswith(("-", "+")):
        return ""
    flags, takes, noexec, _ = spec
    if t in noexec:
        return "noexec"
    if t in takes:
        return "takes"
    if t in flags or t.split("=", 1)[0] in takes or (not t.startswith("--") and t[:2] in takes):
        return "flag"                                  # 값이 붙은 꼴(`--unset=X` · `-n1` · `-I{}`)
    return "other"


def _shell_o(w, nxt) -> str:
    """셸 래퍼의 `-o 값`(붙인 `-o값` 포함)이 noexec 인가 — 'noexec'(구문 검사만) · 'other'(값이 펼쳐져 실행 여부를 모른다) · ''.
    zsh 는 대소문자 · `_` 를 무시한다(`-o NO_EXEC`) — bash 가 거부하는 철자(`-onoexec` · `NOEXEC`)도 오류로 끝나 아무것도 실행하지 않는다
    (2026-11-11 bash · zsh · sh 실측)."""
    if w.quoted or not w.text.startswith("-o"):
        return ""
    v = nxt if w.text == "-o" else w._replace(text=w.text[2:])
    if v is None:
        return ""
    if v.expands:
        return "other"
    return "noexec" if v.text.lower().replace("_", "") == "noexec" else ""


def _resolve(ws, rs, depth, deferred, table):
    via, spec, wi, lead, i = [], None, 0, True, 0

    def cmd(name, args, why=""):
        return Cmd(name, list(args), list(rs), depth, deferred, why, tuple(via))
    if ws and not ws[0].quoted and ws[0].text in _CLOSE:
        return cmd(None, [], "" if len(ws) == 1 else "closer-words")
    while i < len(ws):
        w = ws[i]
        if lead and not w.quoted and w.text in _LEAD:
            i += 1
            continue
        if lead and not w.quoted and w.text in _HEAD:
            ok = (i + 1 < len(ws) and not ws[i + 1].quoted and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ws[i + 1].text)
                  and (i + 2 == len(ws) or (ws[i + 2].text == "in" and not ws[i + 2].quoted)))
            return cmd(None, [], "" if ok else "loop-header")
        if lead and not w.quoted and w.text == "time":    # 예약어 time — 뒤가 아직 명령 자리이고 함수도 부른다(래퍼가 아니다 · via 에 넣지 않는다)
            i += 2 if i + 1 < len(ws) and not ws[i + 1].quoted and ws[i + 1].text == "-p" else 1   # bash 예약어가 받는 옵션은 -p 뿐이다
            continue
        kind = _opt_kind(spec, w) if spec else ""
        if via and via[-1] in SHELL_WRAPPERS and kind in ("takes", "flag"):
            kind = _shell_o(w, ws[i + 1] if i + 1 < len(ws) else None) or kind   # `bash -o noexec` 는 -n 과 같다
        if kind == "noexec":
            return cmd(ws[wi], ws[wi + 1:])            # 조회 · 구문 검사 — 래퍼 자신이 명령이다(뒤 단어는 실행되지 않는다)
        if kind == "other":
            return cmd(None, [], "wrapper-option")
        if kind:
            i += 2 if kind == "takes" else 1
            continue
        if w.assign:
            if spec and not spec[3]:
                return cmd(None, [], "wrapper-assign")  # `nohup X=1 a` — 래퍼는 그 단어를 실행 파일로 찾는다
            lead, i = False, i + 1
            continue
        base = os.path.basename(w.text)
        if not w.expands and base in table:            # 셸은 따옴표를 벗겨 실행한다(`"/usr/bin/env" touch x` 도 env) — 펼쳐지는 이름만 모른다
            spec, wi, lead, i = table[base], i, False, i + 1
            via.append(base)
            continue
        return cmd(w, ws[i + 1:])
    return cmd(ws[wi], ws[wi + 1:]) if spec else cmd(None, [])   # 래퍼만(`env` 는 환경을 찍는다) · 대입 · 예약어만


def commands(toks, shells=False):
    """단순 명령마다 Cmd — 명령 자리 단어를 정한다(예약어 · 루프 머리 · 닫는 말 · 대입 · 래퍼와 그 옵션). 치환 안 명령은 깊이+1 로 뒤에 낸다.
    함수 정의 본문과 함수에 붙은 리다이렉트(`f() { …; } > 대상`)는 deferred 다 — 정의될 때 실행되지 않는다.
    shells=True 면 bash · sh · zsh 도 래퍼로 벗긴다. ⛔ 못 읽은 토큰(Unknown)은 그대로 돌려준다 — 소비자가 보수 판정한다."""
    if is_unknown(toks):
        return toks
    out = []
    _commands(toks, 0, False, {**WRAPPERS, **SHELL_WRAPPERS} if shells else WRAPPERS, out)
    return out


def _commands(toks, depth, deferred, table, out):
    ws, rs, subs, late = [], [], [], False

    def flush():
        if ws or rs:
            c = _resolve(ws, rs, depth, deferred or late, table)
            out.append(c._replace(name=None, args=[], unsure="after-function") if late and ws else c)
        ws.clear()
        rs.clear()
    for t in toks:
        if isinstance(t, Func):
            flush()
            late = True                                # 바로 뒤 리다이렉트는 함수 정의의 일부다
            subs.append((t.body, True))
            continue
        if isinstance(t, Op):
            flush()
            late = False
            continue
        (ws if isinstance(t, Word) else rs).append(t)
        subs.extend((sub, deferred or late) for sub in nested(t)[1])
    flush()
    for sub, d in subs:
        _commands(sub, depth + 1, d, table, out)


def js_template(src, i):
    """`src[i]` 의 JS 템플릿(백틱)을 읽어 (끝 다음 위치, [보간식 원문, …]) — 중첩 중괄호 · 문자열 · 템플릿 · 주석을 따라간다.
    정규식 리터럴은 표 밖이다(나눗셈과 가르지 않는다 — 그 안의 중괄호는 잘못 센다). 못 읽으면 Unknown."""
    try:
        return _js_template(src, i)
    except _Giveup as g:
        return Unknown(g.why, g.pos)
    except RecursionError:
        return Unknown("too-deep", i)


_JS_EOL = "\n\r\u2028\u2029"
_JS_KEYWORDS = frozenset(("typeof", "instanceof", "in", "of", "new", "delete", "void", "return", "throw", "case", "do", "else",
                          "yield", "await"))   # 뒤의 / 는 나눗셈이 아니라 정규식 리터럴이다


def _js_template(src, i):
    if "js-template" not in RULES:
        raise _Giveup("rule-off:js-template", i)
    n, j, exprs = len(src), i + 1, []
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
        elif c == "`":
            return j + 1, exprs
        elif src.startswith("${", j):
            k = _js_expr_end(src, j + 2)
            exprs.append(src[j + 2:k])
            j = k + 1
        else:
            j += 1
    raise _Giveup("js-template-unterminated", i)


def _js_expr_end(src, j):
    n, depth, start = len(src), 0, j
    tok, tok_end = "", -1                   # 마지막 의미 토큰(공백 · 주석 제외) — 문자열 · 템플릿 끝은 '"' · 이어 붙은 식별자 · 숫자는 한 토큰
    while j < n:
        c = src[j]
        if c in "'\"":
            k = j + 1
            while k < n and src[k] != c:
                if src[k] in _JS_EOL:
                    raise _Giveup("js-string-newline", k)
                k += 2 if src[k] == "\\" else 1
            if k >= n:
                raise _Giveup("js-string-unterminated", j)
            j = k + 1
            tok, tok_end = '"', j
            continue
        if c == "`":
            j = _js_template(src, j)[0]
            tok, tok_end = '"', j
            continue
        if src.startswith("//", j):
            k = next((x for x in range(j, n) if src[x] in _JS_EOL), n)   # 줄 주석은 CR · LF · U+2028 · U+2029 에서 끝난다
            j = k
            continue
        if src.startswith("/*", j):
            k = src.find("*/", j + 2)
            if k < 0:
                raise _Giveup("js-comment-unterminated", j)
            j = k + 2
            continue
        if src.startswith(("<!--", "-->"), j):
            raise _Giveup("js-html-comment", j)   # 스크립트 문법에서는 줄 주석이다(그 안의 } 를 잘못 센다)
        if c == "/":
            operand = tok in ("]", '"') or (re.fullmatch(r"[A-Za-z0-9_$]+", tok) is not None and tok not in _JS_KEYWORDS)
            if not operand:
                raise _Giveup("js-regex-literal", j)   # `if (x) /re/` 처럼 ) 뒤 · 피연산자가 아닌 자리는 정규식 리터럴일 수 있다
        if c == "{":
            depth += 1
        elif c == "}":
            if depth == 0:
                return j
            depth -= 1
        if not c.isspace():
            word_char = re.match(r"[A-Za-z0-9_$]", c) is not None
            tok = tok + c if (word_char and tok_end == j and re.fullmatch(r"[A-Za-z0-9_$]+", tok or "-")) else c
            tok_end = j + 1
        j += 1
    raise _Giveup("js-template-expr-unterminated", start)


# ── self-test ────────────────────────────────────────────────────────────────

def _redirs(src):
    toks = lex(src)
    return [(r.op, r.target.text, d) for _w, rs, d in simple_commands(toks) for r in rs] if not is_unknown(toks) else toks


# 규칙마다 그 규칙이 있어야만 통과하는 표본 — 규칙을 지우면 `rule-<이름>` 셀이 실패한다(제거 probe 의 잡는 셀)
COVERAGE = {
    "word": lambda: words("echo hi") == ["echo", "hi"],
    "single-quote": lambda: words("echo 'a;b > c' d") == ["echo", "a;b > c", "d"],
    "double-quote": lambda: words('echo "a \\"b\\" $X"') == ["echo", 'a "b" $X'],
    "ansi-c-quote": lambda: words("cut -d$'\\t' f") == ["cut", "-d\t", "f"],
    "backslash-escape": lambda: words("[ a \\> b ]") == ["[", "a", ">", "b", "]"] and _redirs("[ a \\> b ]") == []
    and words("a \\\n  b") == ["a", "b"],
    "parameter": lambda: words("echo ${X:-/tmp} $1") == ["echo", "${X:-/tmp}", "$1"],
    "command-substitution": lambda: _redirs('echo "$(printf "x" > f)"') == [(">", "f", 1)],
    "backtick-substitution": lambda: _redirs("echo `printf x > f`") == [(">", "f", 1)],
    "arith-expansion": lambda: words("echo $(( 3 > 2 ))") == ["echo", "$(( 3 > 2 ))"],
    "process-substitution": lambda: _redirs("diff <(sort a > s) b") == [(">", "s", 1)],
    "operator": lambda: segments("a && b; c | d") == ["a ", " b", " c ", " d"],
    "redirection": lambda: _redirs("echo x 2>&1 >>out") == [(">&", "1", 0), (">>", "out", 0)] and words("2&>/dev/null x") == ["2", "x"],
    "heredoc": lambda: segments("cat <<'EOF' > o\na; b > c\nEOF\necho z") == ["cat <<'EOF' > o", "echo z"],
    "comment": lambda: words("echo a # b > c") == ["echo", "a"] and _redirs("echo a # b > c") == [],
    "test-command": lambda: _redirs('[[ "$a" > "$b" ]] && echo y') == [],
    "function-definition": lambda: [type(t).__name__ for t in lex("f () { ls; }; f")] == ["Func", "Op", "Word"],
    "arith-command": lambda: _redirs("(( n > 0 )) && echo ok") == [],
    "js-template": lambda: js_template("`a ${f({}) + g()} b`", 0) == (20, ["f({}) + g()"])
    and js_template("`${1 // c\r + g()\n}`", 0)[1] == ["1 // c\r + g()\n"] and js_template("`${a / b}`", 0)[1] == ["a / b"]
    and js_template('`${"8" / 2}`', 0)[1] == ['"8" / 2'],   # 닫는 따옴표 뒤 / 는 나눗셈(r3 3차 ISSUE-009)
}
OUTSIDE = ['echo $"x"', "X=(a b)", 'echo ${X:-"a"}', "echo 'a", "printf x \\>> f", "printf x \\>>> f", "echo $(( $(x) ))",
           "cat <<EOF\nno end", "[[ a =~ (b|c) ]]", "echo $(case x in a) y;; esac)", "echo `a", "cat >",
           # r3 GPT 적대 검토 반례(ISSUE-001 · 002 · 007 · 010 · 011 · 012 · 013) — bash 와 다르게 읽던 꼴은 Unknown 이다
           "printf x > $'a/\\056\\056/pwn'", "cat <<EOF\nE\\\nOF\nprintf x > out\nEOF\n",
           "cat <<$(gpt-call.sh review)\nbody\n$(gpt-call.sh review)\n", "gpt-call.sh review > #comment", "echo x<(printf ok)",
           "printf '<%s>\\n' 2\\\n>&1", "echo `echo \\`printf hi\\``", "printf x >\\\n> f",
           # r3 2차(ISSUE-001 · 002 · 005 · 006)
           "echo ${x:-{a} ; touch target # }", "X\\\n=1 touch target", "false &\\\n\\\n& gpt-call.sh review", "[[ ab =~ a(b) ]]",
           # r3 3차(ISSUE-001 · 002 · 006 · 007)와 같은 부류를 찔러 본 꼴(case 이어짐 · 첨자 공백 · extglob · 산술 for · coproc · 함수 자리)
           'echo "`printf \\"%s\\" \\"x # data\\"; printf x > target`"', "unset x; : ${x:-<(printf x > gates/pl\\an.md)}", "echo $[1 + 2]",
           "cat <<EOF", "case x in a) echo;;& b) echo;; esac", "case x in a) echo;& b) :;; esac", "A[a b]=x tee t", "echo !(x)",
           "echo *(a|b)", "for ((i=0;i<3;i++)); do echo; done", "coproc tee t", "echo foo()",
           "echo $(cat <<EOF)\nx\nEOF", "{fd}>f echo x", "case x in a|b) tee f;; esac",
           # r3 4차(ISSUE-001 · 002 · 003 · 006 · 007)
           '[[ -n <(printf "x" > gates/pl""an.md) ]]', "A[b[0] + 1]=x tee target",
           "function f { gpt-call.sh review; }", "time -p case x in x) :;; esac",
           # 함수 정의 규칙 밖(4차 006 은 이제 규칙 안 — r3-s1-funcdef-body-deferred): function 꼴 · 닫히지 않은 본문 · 본문 꼴 밖 · 짝 없는 )
           "function f() { :; }", "f() { gpt-call.sh review; ", "f() gpt-call.sh review", "f() { a; ) }", "'f'() { :; }"]


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.dirname(here), os.path.dirname(os.path.dirname(os.path.dirname(here)))):
        if all(os.path.isfile(os.path.join(cand, *p)) for p in (("scripts", "gate_stop_hook.py"), ("mods", "fz-guard", "hooks", "guard.py"),
                                                                ("scripts", "check_comment_worthy.py"))):
            return cand
    return None


class _Deny:
    """`import shell_tokens` 를 ImportError 가 아닌 PermissionError 로 실패시키는 찾기 훅(읽기 권한 · 파일 시스템 실패 재현)."""

    def find_spec(self, name, path=None, target=None):
        if name == "shell_tokens":
            raise PermissionError(name)
        return None


def _load(path, name, block=False):
    """소비자 모듈을 이름을 바꿔 읽는다 — block=True 면 `import shell_tokens` 가 ImportError, "perm" 이면 PermissionError 로 실패한다."""
    import importlib.util
    missing = object()
    saved = sys.modules.get("shell_tokens", missing)
    deny = _Deny()
    if block == "perm":
        sys.modules.pop("shell_tokens", None)
        sys.meta_path.insert(0, deny)
    elif block:
        sys.modules["shell_tokens"] = None
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if deny in sys.meta_path:
            sys.meta_path.remove(deny)
        if saved is missing:
            sys.modules.pop("shell_tokens", None)
        else:
            sys.modules["shell_tokens"] = saved


class _Spy:
    """소비자의 `shell_tokens` 자리에 끼워 부른 함수 이름을 모은다."""

    def __init__(self, real):
        self.real, self.calls = real, set()

    def __getattr__(self, name):
        f = getattr(self.real, name)
        if callable(f) and not isinstance(f, type):
            def wrap(*a, **k):
                self.calls.add(name)
                return f(*a, **k)
            return wrap
        return f


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    for rule in sorted(RULES):
        try:
            ok = rule in COVERAGE and COVERAGE[rule]()
        except Exception as e:                 # noqa: BLE001 — 표본이 깨져도 셀 실패로 보인다
            ok = f"{type(e).__name__}: {e}"
        case(f"rule-{rule}", ok is True, ok)
    got = {s: lex(s) for s in OUTSIDE}
    tmpl = [js_template("`${a", 0), js_template("`${ok()`)", 0), js_template('`${"a\nb"}`', 0),
            js_template('`${/[}]/.test("}") ? missingHelper() : 0}`', 0),      # 정규식 리터럴(ISSUE-004)
            js_template("`${typeof /[}]/ + missingHelper()}`", 0),           # 키워드 뒤 정규식(2차 ISSUE-003)
            js_template('`${(() => { if (true) /[}]/.test("x"); return 0; })() + missingHelper()}`', 0),   # ) 뒤 정규식(3차 ISSUE-003)
            js_template("`${1 <!-- }\n + missingHelper()}`", 0),          # HTML 꼴 주석
            js_template("`${void // x\n /[}]/ + missingHelper()}`", 0)]   # 주석 뒤 / — 직전 의미 토큰은 void(4차 ISSUE-004)
    frag = lex("cat <<EOF", fragment=True)           # 조각은 본문이 다른 조각에 있다 — 열린 heredoc 을 본문 없음으로 읽는다
    ufd = lex("\u0662>/dev/null gpt-call.sh review")   # 유니코드 숫자는 fd 가 아니라 명령 단어다(4차 ISSUE-002)
    case("r3-f458-outside-allowlist-unknown — 허용 목록 밖 꼴은 전부 Unknown 이다(차단 목록을 뒤집었다)",
         all(is_unknown(v) for v in got.values()) and all(is_unknown(v) for v in tmpl) and not is_unknown(frag)
         and not is_unknown(ufd) and isinstance(ufd[0], Word) and ufd[0].text == "\u0662",
         [s for s, v in got.items() if not is_unknown(v)] + [v for v in tmpl if not is_unknown(v)] + [frag, ufd])
    # 함수 정의 — 본문은 정의만 되고 실행되지 않는다. 붙여 쓴 · 띄어 쓴 · 줄바꿈 뒤 본문 · 괄호 본문 모두 Func 하나이고, 본문 명령은
    # 깊이 1 로만 나온다(4차 ISSUE-006 의 공백 꼴 `f () {` 가 맨 바깥 명령으로 읽히던 구멍) · 본문 안 `{ …; }` 의 } 는 본문을 닫지 않는다
    fd = {c: lex(c) for c in ("f() { :; gpt-call.sh review; }", "f () { :; gpt-call.sh review; }",
                              "f()\n{\n gpt-call.sh review\n}", "f() ( gpt-call.sh review )", "f() { { a; }; gpt-call.sh review; }")}
    top = {c: [] if is_unknown(t) else [ws[0].text for ws, _r, d in simple_commands(t) if d == 0 and ws] for c, t in fd.items()}
    inner = {c: [] if is_unknown(t) else [ws[0].text for ws, _r, d in simple_commands(t) if d == 1 and ws] for c, t in fd.items()}
    case("r3-s1-funcdef-body-deferred — 함수 정의는 Func 하나 · 본문 명령은 깊이 1(맨 바깥 명령 자리 아님) · 공백 꼴 포함",
         all(not is_unknown(t) and len(t) == 1 and isinstance(t[0], Func) for t in fd.values())
         and all(v == [] for v in top.values()) and all("gpt-call.sh" in v for v in inner.values())
         and segments("g(){ a; b; }; g x") == ["g(){ a; b; }", " g x"], (top, inner))
    want = {("if true; then touch r; fi", False): [("true", False, ""), ("touch", False, ""), (None, False, "")],
            ("for f in a; do rm x; done", False): [(None, False, ""), ("rm", False, ""), (None, False, "")],
            ("! { X=1 env -u Y time -p nohup rm a; }", False): [("rm", False, ""), (None, False, "")],
            ("command -v rm", False): [("command", False, "")], ("nohup X=1 rm a", False): [(None, False, "wrapper-assign")],
            ("env -S x rm a", False): [(None, False, "wrapper-option")], ("fi rm", False): [(None, False, "closer-words")],
            ("for 1 in a", False): [(None, False, "loop-header")], ('"if" rm', False): [("if", False, "")],
            ("f() { rm a; } > $(touch b)", False): [(None, True, ""), ("rm", True, ""), ("touch", True, "")],
            ("f() { :; } x", False): [(None, True, "after-function"), (":", True, "")],
            ("caffeinate -i bash s.sh a", True): [("s.sh", False, "")], ("caffeinate -i bash s.sh a", False): [("bash", False, "")],
            ("bash -c 'x'", True): [(None, False, "wrapper-option")], ("xargs -n1 -I{} rm {}", False): [("rm", False, "")]}
    got = {k: [(x.name.text if x.name else None, x.deferred, x.unsure) for x in commands(lex(k[0]), shells=k[1])] for k in want}
    case("r3-s1-command-position — 명령 자리를 한 곳에서 정한다(예약어 · 루프 머리 · 닫는 말 · 대입 · 래퍼와 옵션 · bash 스크립트) · 함수 본문과 "
         "함수에 붙은 리다이렉트는 지연 · 표 밖 래퍼 옵션 · 래퍼 뒤 대입은 미상 · 못 읽은 토큰은 Unknown 그대로",
         got == want and is_unknown(commands(lex("case x in esac"))), {k: v for k, v in got.items() if v != want[k]})

    def cv(src, shells=False):
        return [(x.name.text if x.name else None, x.via, x.unsure) for x in commands(lex(src), shells=shells)]
    got = [cv('"/usr/bin/env" touch x'), cv("'nohup' rm a"), cv('"$E" touch x')]
    case("r3-s1-r6-001-quoted-wrapper-name — 따옴표 친 래퍼 이름도 래퍼다(셸이 따옴표를 벗긴다) · 펼쳐지는 이름은 모른다",
         got == [[("touch", ("env",), "")], [("rm", ("nohup",), "")], [("$E", (), "")]], got)
    got = [cv(c, True) for c in ("bash -o noexec s.sh review", "zsh -o NO_EXEC s.sh", "bash -onoexec s.sh", 'bash -o "$O" s.sh',
                                 "bash -o xtrace s.sh", "bash +o noexec s.sh")]
    case("r3-s1-r6-010-shell-o-noexec — 셸 래퍼의 -o noexec(철자 · 붙여 쓴 꼴 포함)는 구문 검사만이다 · 펼쳐지는 값은 미상 · 다른 옵션은 실행",
         got == [[("bash", ("bash",), "")], [("zsh", ("zsh",), "")], [("bash", ("bash",), "")], [(None, ("bash",), "wrapper-option")],
                 [("s.sh", ("bash",), "")], [("s.sh", ("bash",), "")]], got)
    got = [cv(c) for c in ("time { cat a; }", "time -p cat a", "time f", '"time" cat a', "env time cat a")]
    case("r3-s1-r6-013-reserved-time — 예약어 time 뒤는 아직 명령 자리다(묶음 · -p) · 래퍼가 아니다(함수도 부른다) · 따옴표 · 래퍼 뒤 time 은 외부 명령",
         got == [[("cat", (), ""), (None, (), "")], [("cat", (), "")], [("f", (), "")], [("cat", ("time",), "")],
                 [("cat", ("env", "time"), "")]], got)
    case("r3-f039-removal-probe-recorded — 규칙마다 잡는 셀이 있다(--list-rules = 표본 표의 규칙)",
         set(COVERAGE) == set(RULES) and all(callable(f) for f in COVERAGE.values()), sorted(set(RULES) ^ set(COVERAGE)))

    root = _repo_root()
    if root is None:
        print("SKIP r3-f458-shared-by-three · r3-no-regex-fallback-on-import-failure — 저장소 밖 사본(소비자 셋이 없다)")
    else:
        paths = {"guard": os.path.join(root, "mods", "fz-guard", "hooks", "guard.py"),
                 "stop": os.path.join(root, "scripts", "gate_stop_hook.py"),
                 "ccw": os.path.join(root, "scripts", "check_comment_worthy.py")}
        me = sys.modules[__name__]
        try:
            g, st, cw = (_load(paths[k], f"_st_probe_{k}") for k in ("guard", "stop", "ccw"))
            spies = {k: _Spy(me) for k in paths}
            g.shell_tokens, st.shell_tokens, cw.shell_tokens = spies["guard"], spies["stop"], spies["ccw"]
            g.bash_write("echo x > a.swift")
            g.gpt_review_invoked("bash gpt-call.sh review")
            st._bash_write_targets("python3 gate_check.py --finalize gates/plan.md", None, [])
            cw._strip_lexemes("rollStep(`${a}`)", False)
            calls = {k: sorted(v.calls) for k, v in spies.items()}
            case("r3-f458-shared-by-three — 세 소비자가 같은 토크나이저 함수를 부른다", all(calls.values()), calls)
        except Exception as e:                 # noqa: BLE001
            case("r3-f458-shared-by-three — 세 소비자가 같은 토크나이저 함수를 부른다", False, f"{type(e).__name__}: {e}")
        try:
            ok, gots = True, []
            for mode in (True, "perm"):                # ImportError · PermissionError(3차 ISSUE-008) 둘 다 보수 판정이다
                g, st, cw = (_load(paths[k], f"_st_block_{k}", block=mode) for k in ("guard", "stop", "ccw"))
                unk = []
                st_out = st._bash_write_targets("python3 gate_check.py --finalize gates/plan.md", None, unk)
                got = {"none": (g.shell_tokens, st.shell_tokens, cw.shell_tokens),
                       "guard": (g.bash_write("echo x > a.swift"), g.gpt_review_invoked("bash gpt-call.sh review")),
                       "stop": (st_out, bool(unk)), "ccw": cw.UNLEXED in cw._strip_lexemes("rollStep(`${missingHelper()}`)", False)}
                ok = ok and (got["none"] == (None, None, None) and got["guard"] == ((True, []), False) and got["stop"] == ([], True)
                             and got["ccw"] is True)
                gots.append(got)
            case("r3-no-regex-fallback-on-import-failure — 토크나이저 import 가 실패하면(ImportError · PermissionError) 소비자 셋이 정규식으로 돌아가지 않고 보수 판정으로 끝난다",
                 ok, gots)
        except Exception as e:                 # noqa: BLE001
            case("r3-no-regex-fallback-on-import-failure", False, f"{type(e).__name__}: {e}")
    print(f"shell_tokens self-test {sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    if "--list-rules" in sys.argv[1:]:
        print("\n".join(sorted(RULES)))
        sys.exit(0)
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    print(__doc__.strip(), file=sys.stderr)
    sys.exit(2)
