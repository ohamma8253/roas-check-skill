"""점검 결과(result.json)를 '점검 이력판' 대시보드 한 장(HTML)으로 그린다.

  python3 render_board.py --run RUN_DIR [--out board.html] [--v3 | --v2 | --v1]

v4(기본): 점검 이력판 — 줄 = 자리(신호판 · 시장 · 자사 · 매체, 레이어 머리줄 = 관문 답), 칸 = 지난 날(데일리 13일) · 주(위클리 7주),
  오른쪽 끝 = 이번 점검. 지난 칸은 같은 광고주 폴더의 다른 실행 폴더(result.json, 같은 리듬)에서 모은다. 실행이 없는 날은 빗금.
  판정 띠(원인 자리 · 할 일 · 체크리스트 진행 · ROAS 흐름), 체크리스트 채우기(브라우저에 저장), 할 일 · 빈 곳 탭,
  진행 순서 탭(v4.1: 스킬의 카드 흐름 — 데일리 0~6 · 위클리 W1~W3, 이번 실행 자취와 이력판 줄로 가기). 화면 틀은 board_template.html.
v3: 평면 점검 회로(신호판 → 관문 → 자리 카드) + 체크리스트 채우기(board_template_v3.html).
v2: 평면 회로도 + 점검반 램프(board_template_v2_flat.html). v1: 3D로 쌓은 판(board_template_v1_3d.html). 체크리스트 목록은 checklist.json(tools/gen_checklist.py가 만든다).
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import load  # noqa: E402

HERE = Path(__file__).parent


def history(run, res):
    """같은 광고주 폴더의 다른 실행(같은 리듬, 이번 날짜 이전, 데일리 13일 · 위클리 7주 안)을 모은다."""
    weekly = res.get("rhythm") == "weekly"
    now = date.fromisoformat(res["date"])
    since = now - timedelta(days=49 if weekly else 13)
    out = {}
    for d in run.parent.iterdir():
        f = d / "result.json"
        if d.resolve() == run.resolve() or not f.is_file():
            continue
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            day = date.fromisoformat(r["date"])
        except (ValueError, KeyError):
            continue
        if r.get("rhythm") != res.get("rhythm") or not since <= day < now:
            continue
        sig = r.get("signal") or {}
        out[r["date"]] = {"date": r["date"], "roas": sig.get("roas_now") if not weekly else ((r.get("weeks") or [{}])[0].get("roas")),
                          "checks": [{"node": c["node"], "status": c["status"]} for c in r.get("checks", [])]}
    return [out[k] for k in sorted(out)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out")
    ap.add_argument("--v1", action="store_true", help="예전 3D 화면으로 그린다")
    ap.add_argument("--v2", action="store_true", help="예전 평면 회로도(v2)로 그린다")
    ap.add_argument("--v3", action="store_true", help="평면 점검 회로(v3.1)로 그린다")
    a = ap.parse_args()
    run = Path(a.run)
    res = load(run, "result.json")
    if not res:
        raise SystemExit("result.json이 없다. analyze.py를 먼저 돌린다.")
    cat = json.loads((HERE / "checklist.json").read_text(encoding="utf-8"))
    dump = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    tpl = HERE / ("board_template_v1_3d.html" if a.v1 else "board_template_v2_flat.html" if a.v2
                  else "board_template_v3.html" if a.v3 else "board_template.html")
    html = (tpl.read_text(encoding="utf-8").replace("__DATA__", dump(res)).replace("__CAT__", dump(cat))
            .replace("__HIST__", dump(history(run, res))))
    out = Path(a.out) if a.out else run / "board.html"
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
