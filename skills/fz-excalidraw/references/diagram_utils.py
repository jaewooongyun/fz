"""
diagram_utils.py — Excalidraw JSON 생성 헬퍼 모듈

사용법:
    from diagram_utils import D, rect, txt, arr, ln, ellipse, diamond, elbow_arrow, hstack, vstack, code_box, save

주의: arr()에 label 파라미터 없음 — 화살표 레이블은 별도 txt()로 배치할 것 (Anti-Overlap 규칙 1)
"""

import json, math, random

# ─── 전역 요소 버퍼 ──────────────────────────────────────────────────────────
_elements: list[dict] = []
_id_counter = 1000


def reset():
    """새 다이어그램 시작 시 버퍼 초기화"""
    global _elements, _id_counter
    _elements = []
    _id_counter = 1000


def _id() -> str:
    global _id_counter
    _id_counter += 1
    return f"el{_id_counter}"


def _seed() -> int:
    return random.randint(10000, 99999)


# ─── 텍스트 폭 계산 (Anti-Overlap 규칙 3) ───────────────────────────────────

def text_width(text: str, font_size: int = 12) -> int:
    """글자 수 기반 텍스트 폭 계산. 한글 ≈ fs*0.9, 영문 ≈ fs*0.55"""
    has_korean = any('\uAC00' <= c <= '\uD7A3' for c in text)
    char_w = font_size * 0.85 if has_korean else font_size * 0.6
    return max(60, int(len(text) * char_w))


def _rect_w(label: str, font_size: int, padding: int = 20) -> int:
    return max(120, text_width(label, font_size) + padding)


# ─── 기본 요소 헬퍼 ─────────────────────────────────────────────────────────

def rect(x, y, w, h, fill, stroke, label=None, fs=13, text_color=None, dashed=False):
    """
    Rectangle. label은 단일 줄만 지원.
    multi-line이 필요하면 rect() 후 별도 txt()를 boundElements로 연결 대신 자유 텍스트로 배치.
    """
    eid = _id()
    el = {
        "type": "rectangle", "id": eid,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": fill,
        "fillStyle": "solid", "strokeWidth": 2,
        "strokeStyle": "dashed" if dashed else "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": [], "link": None, "locked": False,
        "roundness": {"type": 3}
    }
    _elements.append(el)

    if label:
        tc = text_color or "#374151"
        lines = label.split("\\n")
        n = len(lines)
        line_h = fs * 1.35
        total_h = n * line_h
        ty = y + (h - total_h) / 2  # 수직 중앙 (multi-line 지원)
        tid = _id()
        txt_el = {
            "type": "text", "id": tid,
            "x": x + 6, "y": ty,
            "width": w - 12, "height": total_h,
            "text": label.replace("\\n", "\n"),
            "originalText": label.replace("\\n", "\n"),
            "fontSize": fs, "fontFamily": 3,
            "textAlign": "center", "verticalAlign": "middle",
            "strokeColor": tc, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100, "angle": 0,
            "seed": _seed(), "version": 1, "versionNonce": _seed(),
            "isDeleted": False, "groupIds": [],
            "boundElements": None, "link": None, "locked": False,
            "containerId": eid, "lineHeight": 1.25
        }
        el["boundElements"].append({"id": tid, "type": "text"})
        _elements.append(txt_el)

    return eid


def ellipse(x, y, w, h, fill, stroke, label=None, fs=13, text_color=None):
    """Ellipse / circle"""
    eid = _id()
    el = {
        "type": "ellipse", "id": eid,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": fill,
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": [], "link": None, "locked": False
    }
    _elements.append(el)

    if label:
        tc = text_color or "#374151"
        tid = _id()
        txt_el = {
            "type": "text", "id": tid,
            "x": x + 6, "y": y + (h - fs * 1.25) / 2,
            "width": w - 12, "height": fs * 1.25,
            "text": label, "originalText": label,
            "fontSize": fs, "fontFamily": 3,
            "textAlign": "center", "verticalAlign": "middle",
            "strokeColor": tc, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100, "angle": 0,
            "seed": _seed(), "version": 1, "versionNonce": _seed(),
            "isDeleted": False, "groupIds": [],
            "boundElements": None, "link": None, "locked": False,
            "containerId": eid, "lineHeight": 1.25
        }
        el["boundElements"].append({"id": tid, "type": "text"})
        _elements.append(txt_el)

    return eid


def diamond(x, y, w, h, fill, stroke, label=None, fs=13, text_color=None):
    """Diamond / decision shape"""
    eid = _id()
    el = {
        "type": "diamond", "id": eid,
        "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": fill,
        "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": [], "link": None, "locked": False
    }
    _elements.append(el)

    if label:
        tc = text_color or "#374151"
        lines = label.split("\\n")
        n = len(lines)
        line_h = fs * 1.35
        total_h = n * line_h
        ty = y + (h - total_h) / 2
        tid = _id()
        txt_el = {
            "type": "text", "id": tid,
            "x": x + 10, "y": ty,
            "width": w - 20, "height": total_h,
            "text": label.replace("\\n", "\n"),
            "originalText": label.replace("\\n", "\n"),
            "fontSize": fs, "fontFamily": 3,
            "textAlign": "center", "verticalAlign": "middle",
            "strokeColor": tc, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 0, "opacity": 100, "angle": 0,
            "seed": _seed(), "version": 1, "versionNonce": _seed(),
            "isDeleted": False, "groupIds": [],
            "boundElements": None, "link": None, "locked": False,
            "containerId": eid, "lineHeight": 1.25
        }
        el["boundElements"].append({"id": tid, "type": "text"})
        _elements.append(txt_el)

    return eid


def txt(x, y, w, h, text, fs=13, c="#374151", align="left"):
    """Free-floating text (no container). Anti-Overlap 기본 패턴."""
    eid = _id()
    el = {
        "type": "text", "id": eid,
        "x": x, "y": y, "width": w, "height": h,
        "text": text, "originalText": text,
        "fontSize": fs, "fontFamily": 3,
        "textAlign": align, "verticalAlign": "top",
        "strokeColor": c, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": None, "link": None, "locked": False,
        "containerId": None, "lineHeight": 1.25
    }
    _elements.append(el)
    return eid


def ln(x1, y1, x2, y2, c="#64748b", sw=1, dashed=False):
    """Structural line (non-arrow). 수직/수평 분리선, 트리 구조에 사용."""
    eid = _id()
    dx, dy = x2 - x1, y2 - y1
    el = {
        "type": "line", "id": eid,
        "x": x1, "y": y1, "width": abs(dx), "height": abs(dy),
        "strokeColor": c, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": sw,
        "strokeStyle": "dashed" if dashed else "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": None, "link": None, "locked": False,
        "points": [[0, 0], [dx, dy]]
    }
    _elements.append(el)
    return eid


def arr(x1, y1, x2, y2, c="#1e3a5f", sw=2, dashed=False,
        start_id=None, end_id=None):
    """
    직선 화살표 (수직/수평 전용). 대각선 금지 (Anti-Overlap 규칙 2).

    ⚠️ label 파라미터 없음. 화살표 레이블은 반드시 별도 txt()로 배치:
        arr(x1, y1, x2, y2)
        # 수직 화살표: 오른쪽에 레이블
        txt(max(x1,x2)+6, (y1+y2)//2-8, 80, 16, "label", fs=10, c="#64748b")
        # 수평 화살표: 위쪽에 레이블
        txt((x1+x2)//2-30, min(y1,y2)-18, 60, 14, "label", fs=10, c="#64748b")
    """
    eid = _id()
    dx, dy = x2 - x1, y2 - y1
    el = {
        "type": "arrow", "id": eid,
        "x": x1, "y": y1, "width": abs(dx), "height": abs(dy),
        "strokeColor": c, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": sw,
        "strokeStyle": "dashed" if dashed else "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": None, "link": None, "locked": False,
        "points": [[0, 0], [dx, dy]],
        "startBinding": {"elementId": start_id, "focus": 0, "gap": 2} if start_id else None,
        "endBinding": {"elementId": end_id, "focus": 0, "gap": 2} if end_id else None,
        "startArrowhead": None,
        "endArrowhead": "arrow"
    }
    _elements.append(el)
    return eid


def elbow_arrow(x1, y1, x2, y2, turn_x=None, turn_y=None,
                c="#1e3a5f", sw=2, dashed=False):
    """
    L자형 엘보우 화살표. 수직→수평 or 수평→수직 꺾임 (Anti-Overlap 규칙 2).

    turn_y 지정 시: (x1,y1) → (x1,turn_y) → (x2,turn_y) → (x2,y2)  [수직-수평-수직]
    turn_x 지정 시: (x1,y1) → (turn_x,y1) → (turn_x,y2)             [수평-수직]
    둘 다 None이면 중간 y로 자동 계산.
    """
    eid = _id()
    if turn_y is not None:
        pts = [[0, 0], [0, turn_y - y1], [x2 - x1, turn_y - y1], [x2 - x1, y2 - y1]]
    elif turn_x is not None:
        pts = [[0, 0], [turn_x - x1, 0], [turn_x - x1, y2 - y1]]
    else:
        mid_y = (y1 + y2) / 2
        pts = [[0, 0], [0, mid_y - y1], [x2 - x1, mid_y - y1], [x2 - x1, y2 - y1]]

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    el = {
        "type": "arrow", "id": eid,
        "x": x1, "y": y1, "width": dx, "height": dy,
        "strokeColor": c, "backgroundColor": "transparent",
        "fillStyle": "solid", "strokeWidth": sw,
        "strokeStyle": "dashed" if dashed else "solid",
        "roughness": 0, "opacity": 100, "angle": 0,
        "seed": _seed(), "version": 1, "versionNonce": _seed(),
        "isDeleted": False, "groupIds": [],
        "boundElements": None, "link": None, "locked": False,
        "points": pts,
        "startBinding": None, "endBinding": None,
        "startArrowhead": None, "endArrowhead": "arrow"
    }
    _elements.append(el)
    return eid


# ─── 레이아웃 헬퍼 ──────────────────────────────────────────────────────────

def hstack(labels, x_start, y, item_w, item_h, gap=20,
           fill="#3b82f6", stroke="#1e3a5f", fs=12, text_color=None, dashed=False):
    """
    가로 스택. 동일한 스타일의 노드 N개를 좌→우로 배치.
    반환: [(eid, cx, cy), ...] — 각 노드의 id와 중심 좌표

    형제 노드 gap ≥ 20px 강제 (Anti-Overlap 규칙 4).
    """
    assert gap >= 20, "Anti-Overlap 규칙 4: 형제 노드 간 gap ≥ 20px"
    results = []
    for i, label in enumerate(labels):
        x = x_start + i * (item_w + gap)
        eid = rect(x, y, item_w, item_h, fill, stroke, label, fs,
                   text_color=text_color, dashed=dashed)
        cx = x + item_w / 2
        cy = y + item_h / 2
        results.append((eid, cx, cy))
    return results


def vstack(labels, x, y_start, item_w, item_h, gap=20,
           fill="#3b82f6", stroke="#1e3a5f", fs=12, text_color=None, dashed=False):
    """
    세로 스택. 동일한 스타일의 노드 N개를 위→아래로 배치.
    반환: [(eid, cx, cy), ...] — 각 노드의 id와 중심 좌표

    형제 노드 gap ≥ 20px 강제 (Anti-Overlap 규칙 4).
    """
    assert gap >= 20, "Anti-Overlap 규칙 4: 형제 노드 간 gap ≥ 20px"
    results = []
    for i, label in enumerate(labels):
        y = y_start + i * (item_h + gap)
        eid = rect(x, y, item_w, item_h, fill, stroke, label, fs,
                   text_color=text_color, dashed=dashed)
        cx = x + item_w / 2
        cy = y + item_h / 2
        results.append((eid, cx, cy))
    return results


# ─── Evidence Artifact ──────────────────────────────────────────────────────

def code_box(x, y, w, lines: list[str], title=None, fs=11):
    """
    코드/JSON 스니펫 박스. 다크 배경 + 모노스페이스.
    lines: 각 줄 텍스트 목록
    """
    line_h = fs * 1.4
    title_h = 22 if title else 0
    h = title_h + len(lines) * line_h + 16

    # 배경 박스
    rect(x, y, w, h, "#1e293b", "#334155")

    # 타이틀
    if title:
        txt(x + 10, y + 8, w - 20, 16, title, fs=10, c="#94a3b8")

    # 코드 라인
    for i, line in enumerate(lines):
        ty = y + title_h + 8 + i * line_h
        txt(x + 10, ty, w - 20, line_h, line, fs=fs, c="#22c55e")

    return h  # 실제 높이 반환 (다음 요소 y 계산용)


# ─── 출력 ────────────────────────────────────────────────────────────────────

def save(path: str):
    """현재 버퍼를 .excalidraw 파일로 저장"""
    data = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": _elements,
        "appState": {
            "viewBackgroundColor": "#ffffff",
            "gridSize": 20
        },
        "files": {}
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(_elements)} elements → {path}")


# ─── 편의 네임스페이스 (D.rect, D.txt 등) ───────────────────────────────────

class D:
    """namespace alias: from diagram_utils import D"""
    reset = staticmethod(reset)
    rect = staticmethod(rect)
    ellipse = staticmethod(ellipse)
    diamond = staticmethod(diamond)
    txt = staticmethod(txt)
    ln = staticmethod(ln)
    arr = staticmethod(arr)
    elbow_arrow = staticmethod(elbow_arrow)
    hstack = staticmethod(hstack)
    vstack = staticmethod(vstack)
    code_box = staticmethod(code_box)
    save = staticmethod(save)
    text_width = staticmethod(text_width)
