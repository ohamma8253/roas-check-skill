"""점검 결과(result.json)를 '점검 이력판' 대시보드 한 장(HTML)으로 그린다.

  python3 render_board.py --run RUN_DIR [--out board.html] [--v3 | --v2 | --v1]
  python3 render_board.py --blank --out board.html      # 예시 데이터 없이 여는 붙여넣기 전용 판(v4.2~)

v4(기본): 점검 이력판 — 줄 = 자리(신호판 · 시장 · 자사 · 매체, 레이어 머리줄 = 관문 답), 칸 = 지난 날(데일리 13일) · 주(위클리 7주),
  오른쪽 끝 = 이번 점검. 지난 칸은 같은 광고주 폴더의 다른 실행 폴더(result.json, 같은 리듬)에서 모은다. 실행이 없는 날은 빗금.
  판정 띠(원인 자리 · 할 일 · 체크리스트 진행 · ROAS 흐름), 체크리스트 채우기(브라우저에 저장), 할 일 · 빈 곳 탭,
  진행 순서 탭(v4.1: 스킬의 카드 흐름 — 데일리 0~6 · 위클리 W1~W3, 이번 실행 자취와 이력판 줄로 가기),
  스킬 결과 붙여넣기(v4.2: 스킬이 낸 ```roas-check 결과 블록을 읽어 다시 그리고, 그 브라우저에 광고주 · 리듬 · 날짜별로 저장해 지난 칸으로 쓴다.
  형식은 docs/결과블록_형식.md; v4.3: 이번 리듬에 없는 질문이 같은 자리의 다른 리듬 체크리스트 질문과 같으면 그 항목으로 맞추고,
  자리 상태에만 반영 — 체크리스트 진행 숫자에는 넣지 않는다; v4.4: 블록 판정을 '스킬이 봄'으로 채움에 세고, 결론이 난 판은
  '더 보면 좋은 것'으로 낮춤 · 같은 열쇠는 바꿔 쓰기 / 따로 남기기를 고름 · 메모 · 원인 길 단위를 이력판 줄에 · 원인 자리 든 관문 문구).
  v4.5: 할 일 탭도 급함만 · 이유 있는 안 봄을 이력판 줄에 · 진행 순서 카드 1 · 2를 근거 · 원인 길과 같은 말로 · 같은 내용이면 메모를 바꾸지 않음 ·
  피드백 고르기(저장 항목) · 조사를 받침에 맞춤.
  v4.6: 바꿔 쓰기는 블록만 새것으로(빈 메모 · 피드백 칸이면 저장된 것을 이어받음) · 터미널 화면 글(앞 공백 · 줄 끊김 · 오른쪽 창 글)을
  다듬어 같은 블록을 같은 내용으로 알아봄 · 파일에서 읽기(.json) · 진행 칩 '안 봄'과 '비어 있음'을 나눠 셈 · 카드 1 구매 전환율 갈래 하나 고르기 ·
  진행 순서 카드 숫자는 이력판과 같게(다른 리듬은 따로).
  v4.7: 링크로 들어온 결과 바로 읽기 — 주소 #r=1.<crc32>.<base64url(zlib(블록 JSON))>를 풀어 붙이기와 같은 길로 읽고 저장한 뒤
  주소에서 지운다(잘림 · crc 틀림 · 모르는 형식 판이면 알리고 붙여넣기 칸을 연다, 아무것도 저장하지 않음). 형식은 docs/결과블록_형식.md 8절.
  v4.8: 받는 사람이 바로 읽히게 — 머리에 점검일(크게) · 광고주 · 리듬, 바로 아래 판정 띠(원인 자리 · 할 일). '붙인 때'는 '받은 때',
  읽기 결과는 접어 판정 띠 아래로, 결론이 난 판의 진행은 '스킬이 본 것 n · 원인 길 밖 n · 원인 길 위 남은 것 n'. 같은 날 고르기는
  같은 점검(매체 · 비교 · 신호판 ROAS)을 고친 판이면 '이 칸 바꿔 쓰기'를 앞 · 강조로 하고 다른 줄 수를 보인다. 이력 0~1개면 다른 브라우저 안내.
  머리에 '스킬 받기 · 쓰는 법' 링크(누를 때만). 피드백 말은 스킬과 같게(맞음 · 일부 맞음 · 원인 다름 · 아직, 예전 '틀림'도 읽음).
  관문 '안 봄'은 '안 봄'으로, 블록이 다루지 않은 빈 점검은 '비어 있음'으로.
  v4.9: 같은 날 고르기는 원인 자리 · 할 일 · 점검 줄(절반 넘게 다르면)까지 보고 '고친 판'을 가른다. 메모 · 피드백이 붙은 칸은
  강조하지 않는다. 숫자 없는 날(신호판 숫자 · 원인 길 없음)의 원인 자리에 '가설 · 숫자 없음' 띠, 원인 자리가 없으면 '숫자 없음 — 가설은 할 일 · 근거에'.
  자사 관문 답은 신호판 줄로 옮기지 않고, 시장 관문은 신호판 업종 줄이 있으면 그 상태를 따른다(통과여도).
  화면 틀은 board_template.html.
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
    ap.add_argument("--run")
    ap.add_argument("--blank", action="store_true", help="예시 데이터 없이 붙여넣기 전용 판을 그린다(--out 필요)")
    ap.add_argument("--out")
    ap.add_argument("--v1", action="store_true", help="예전 3D 화면으로 그린다")
    ap.add_argument("--v2", action="store_true", help="예전 평면 회로도(v2)로 그린다")
    ap.add_argument("--v3", action="store_true", help="평면 점검 회로(v3.1)로 그린다")
    a = ap.parse_args()
    cat = json.loads((HERE / "checklist.json").read_text(encoding="utf-8"))
    dump = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    if a.blank:
        if not a.out:
            raise SystemExit("--blank에는 --out이 필요하다.")
        html = ((HERE / "board_template.html").read_text(encoding="utf-8").replace("__DATA__", "null")
                .replace("__CAT__", dump(cat)).replace("__HIST__", "[]"))
        Path(a.out).write_text(html, encoding="utf-8")
        print(a.out)
        return
    if not a.run:
        raise SystemExit("--run RUN_DIR이 필요하다(붙여넣기 전용 판은 --blank).")
    run = Path(a.run)
    res = load(run, "result.json")
    if not res:
        raise SystemExit("result.json이 없다. analyze.py를 먼저 돌린다.")
    tpl = HERE / ("board_template_v1_3d.html" if a.v1 else "board_template_v2_flat.html" if a.v2
                  else "board_template_v3.html" if a.v3 else "board_template.html")
    html = (tpl.read_text(encoding="utf-8").replace("__DATA__", dump(res)).replace("__CAT__", dump(cat))
            .replace("__HIST__", dump(history(run, res))))
    out = Path(a.out) if a.out else run / "board.html"
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
