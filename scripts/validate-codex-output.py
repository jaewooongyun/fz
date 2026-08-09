#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 검사 대상과 스키마를 모두 **인자로** 받고
#   로드 실패는 exit 1/2로 낸다 (lint #N6 면제 형태 c).
"""codex 출력이 **fz 스키마 계약**을 지키는지 검사한다 (codex-exec.sh 사후 게이트).

⛔ 설계 전환 (2026-08-10, 4라운드 감사 ISSUE-002·003·004 + Codex C3 권고):
   1·2차 구현은 **범용 JSON Schema 검증기를 자작**했고 그 방향은 실패했다 —
     · `$ref` 형제 병합을 `dict.update` 로 구현 → draft2020-12 는 참조와 형제 제약을 **독립 적용**하는데
       덮어써서 로컬 `minimum:-5` 가 참조 `minimum:0` 을 지우고 `-2` 를 통과시켰다
     · `pattern`·`additionalProperties`(스키마 객체)·미지 `type` 이름을 **조용히 통과**시켰다
     · 고치려 들면 `allOf`/`oneOf`/`unevaluated*` 가 줄줄이 따라온다 (반응적 확장)
   ⇒ **범용성을 포기한다.** fz 스키마는 우리가 소유하므로 *그것들이 실제 쓰는 구조만* 검증한다.
      이건 일반 JSON Schema 검증기가 **아니다**.

지원 키워드는 **실측 기반**이다 (schemas/*.json 전수, 2026-08-10):
   type 162 · description 107 · enum 24 · properties 22 · items 21 · required 17 ·
   additionalProperties 11 · pattern 7 · minimum 6 · $schema/$id/title 5 · format 5 ·
   maximum 4 · $comment 4 · $defs 1 · maxItems 1 · **`$ref` 0건**
   → `$ref` 해소 로직을 **삭제**했다. 값은 인라인해야 하고 그 정합은 lint `#N1` 이 본다.

⛔ **미지원 키워드를 만나면 exit 2**(스키마 문제)로 올린다 — 조용히 통과시키지 않는다.
   `format` 은 **주석 취급**(JSON Schema 기본 동작과 동일) 이며 그 사실을 여기 명시한다.

exit: 0=계약 충족 / 1=출력이 계약 위반 / 2=스키마 문제·사용법 (출력 탓 아님)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "number": (int, float), "integer": int, "null": type(None),
}
# 검증에 쓰는 키워드
ENFORCED = {"type", "properties", "required", "enum", "items",
            "additionalProperties", "pattern", "minimum", "maximum", "maxItems", "minItems"}
# 주석·메타 — 검증하지 않는다는 것을 **명시적으로** 선언한다
ANNOTATION = {"description", "title", "$schema", "$id", "$comment", "$defs", "format", "default"}
KNOWN = ENFORCED | ANNOTATION


class SchemaError(Exception):
    """스키마 자체의 문제 — 출력 탓이 아니므로 exit 2."""


def check_supported(spec: dict, path: str) -> None:
    """⛔ 미지원 키워드에 침묵하지 않는다 (ISSUE-002: `pattern` 무시로 'BAD' 가 통과했다)."""
    unknown = sorted(set(spec) - KNOWN)
    if unknown:
        raise SchemaError(f"{path or '<root>'}: 미지원 키워드 {unknown} — 본 검증기는 fz 스키마 "
                          f"구조만 해석한다 (범용 JSON Schema 아님). 스키마를 지원 집합으로 "
                          f"바꾸거나 검증기에 해당 키워드를 **명시 구현**하라")
    t = spec.get("type")
    for name in (t if isinstance(t, list) else [t] if t is not None else []):
        if name not in TYPES:
            raise SchemaError(f"{path or '<root>'}: 미지 type 이름 {name!r}")
    ap = spec.get("additionalProperties")
    if ap is not None and ap is not False:
        raise SchemaError(f"{path or '<root>'}: additionalProperties 는 `false` 만 지원 (받은 값 {ap!r})")
    pat = spec.get("pattern")
    if pat is not None:
        try:
            re.compile(pat)
        except re.error as e:
            raise SchemaError(f"{path or '<root>'}: pattern 컴파일 실패 {pat!r}: {e}") from e


def type_ok(value, spec) -> bool:
    for name in (spec if isinstance(spec, list) else [spec]):
        if name in ("number", "integer") and isinstance(value, bool):
            continue                                    # bool 은 숫자로 인정하지 않는다
        if isinstance(value, TYPES[name]):
            return True
    return False


def validate(value, spec: dict, path: str) -> list[str]:
    if not isinstance(spec, dict):
        raise SchemaError(f"{path or '<root>'}: 스키마 노드가 객체가 아니다 ({type(spec).__name__})")
    check_supported(spec, path)
    errs: list[str] = []
    here = path or "<root>"

    if "type" in spec and not type_ok(value, spec["type"]):
        return [f"{here}: type {spec['type']} 위반 (실제 {type(value).__name__})"]

    if "enum" in spec and value not in spec["enum"]:
        errs.append(f"{here}: enum {spec['enum']} 에 없는 값 {value!r}")

    if isinstance(value, str) and "pattern" in spec:
        if not re.search(spec["pattern"], value):
            errs.append(f"{here}: pattern {spec['pattern']!r} 불일치 ({value!r})")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        lo, hi = spec.get("minimum"), spec.get("maximum")
        if lo is not None and value < lo:
            errs.append(f"{here}: minimum {lo} 위반 ({value})")
        if hi is not None and value > hi:
            errs.append(f"{here}: maximum {hi} 위반 ({value})")

    if isinstance(value, dict):
        props = spec.get("properties") or {}
        for req in spec.get("required") or []:
            if req not in value:
                errs.append(f"{path}/{req}: required 키 부재")
        if spec.get("additionalProperties") is False:
            for k in value:
                if k not in props:
                    errs.append(f"{path}/{k}: additionalProperties=false 인데 미정의 키")
        for k, sub in props.items():
            if k in value:
                errs += validate(value[k], sub, f"{path}/{k}")

    elif isinstance(value, list):
        lo, hi = spec.get("minItems"), spec.get("maxItems")
        if isinstance(lo, int) and len(value) < lo:
            errs.append(f"{here}: minItems {lo} 위반 (길이 {len(value)})")
        if isinstance(hi, int) and len(value) > hi:
            errs.append(f"{here}: maxItems {hi} 위반 (길이 {len(value)})")
        item = spec.get("items")
        if isinstance(item, dict):
            for i, el in enumerate(value):
                errs += validate(el, item, f"{path}[{i}]")
        elif item is not None:
            raise SchemaError(f"{here}: `items` 는 객체형만 지원 (tuple validation 미지원)")
    return errs


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate-codex-output.py <output.json> <schema.json>", file=sys.stderr)
        return 2
    out_p, schema_p = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        data = json.loads(out_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"⛔ 출력 로드 실패: {e}", file=sys.stderr)
        return 1
    try:
        schema = json.loads(schema_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"⛔ 스키마 로드 실패: {e}", file=sys.stderr)
        return 2

    try:
        errs = validate(data, schema, "")
    except SchemaError as e:
        print(f"⛔ 스키마 문제 (출력 탓이 아니다): {e}", file=sys.stderr)
        return 2
    except RecursionError:
        print("⛔ 재귀 한도 초과 — 순환 스키마 의심", file=sys.stderr)
        return 2

    if errs:
        print(f"⛔ 계약 위반 {len(errs)}건:", file=sys.stderr)
        for e in errs[:20]:
            print(f"   {e}", file=sys.stderr)
        return 1

    n = len(data.get("issues", [])) if isinstance(data.get("issues"), list) else "?"
    print(f"GATE-PASS contract_ok issues={n} verdict={data.get('verdict')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
