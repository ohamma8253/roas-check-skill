"""점검 실행 — 실행 폴더의 데이터로 데일리 또는 위클리 점검을 돌려 result.json · report.md를 만든다.

  python3 analyze.py --run RUN_DIR --date 2026-10-22 [--weekly] [--advertiser A사]

데이터가 없는 자리는 '못 봄'으로 남는다. 판정 기준은 references/checklist.md와 같다.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from daily import Data, run_daily  # noqa: E402
from lib import NODE_NAME, STATUS_NAME, STATUS_ORDER, d, pct, save, won  # noqa: E402
from weekly import FACTOR_NAME, run_weekly  # noqa: E402

SOURCES = [  # 연결 상태 판 — 무엇이 있어야 어느 자리가 켜지나
    ("insights.json", "메타 성과(하루 단위)", "광고 관리자 내보내기 · 메타 API", ["G", "J1", "J4", "J5", "M4"]),
    ("meta.json", "메타 설정 스냅샷", "메타 API", ["M1", "M2", "M3", "M4"]),
    ("snapshots/", "앞선 스냅샷", "다음 실행부터 자동", ["M2", "M3", "M4"]),
    ("activities.json", "메타 변경 이력", "메타 API · 광고 관리자 활동 기록", ["M1", "M2", "M3", "M4"]),
    ("insights_weekly.json", "주 단위 성과(빈도 · 도달)", "메타 API(주 단위로 받기)", ["M3", "M4"]),
    ("pixel.json", "픽셀 이벤트 수", "메타 API(7일치만 남으니 매일 받기)", ["JT"]),
    ("web.json", "웹 점검기", "사이트 자동 점검 · 휴대폰으로 직접 확인", ["J1", "J2", "J3", "JT"]),
    ("site.json", "자사몰 매출 · 행사 달력", "광고주 공유 · 직접 입력", ["G", "J6", "M2", "S1"]),
    ("peers.json", "같은 업종 광고주 묶음", "직접 운영하는 계정", ["S4"]),
    ("search.json", "검색 수요", "네이버 데이터랩 · 구글 트렌드", ["S2"]),
    ("ga4.json", "GA4 단계 · 랜딩별 전환", "GA4 Data API", ["J2", "J5"]),
]
ALL_NODES = list(NODE_NAME)


def connected(run: Path, name: str):
    p = run.parent / "snapshots" if name == "snapshots/" else run / name
    return p.exists() and (not p.is_dir() or any(p.iterdir()))


def node_status(checks):
    out = {n: "na" for n in ALL_NODES}
    for c in checks:
        if STATUS_ORDER[c["status"]] > STATUS_ORDER[out.get(c["node"], "na")]:
            out[c["node"]] = c["status"]
    return out


def report(res):
    L = [f"# ROAS 점검 — {res['advertiser']} · 메타 · {res['date']} · {'위클리' if res['rhythm'] == 'weekly' else '데일리'}", ""]
    sig = res.get("signal")
    if sig:
        L.append(f"**신호판** 어제 ROAS {pct(sig['roas_now'])} · 앞 {sig['base_days']}일 {pct(sig['roas_base'])} · 광고비 {won(sig['spend_now'])} · 매출 {won(sig['revenue_now'])}")
        L.append("어느 숫자가: " + " | ".join(f"{FACTOR_NAME[k]} {pct(v['change'], 1)}" for k, v in sig["factors"].items()))
    loc = res.get("location")
    if loc and loc.get("trail"):
        L.append("")
        L.append("**원인 자리 찾기**")
        for t in loc["trail"]:
            kids = ", ".join(f"{k['name']} 몫 {pct(k.get('share'))}" for k in t["children"][:3])
            L.append(f"- {t['unit']['name']}: {t['decision']}" + (f" ({kids})" if kids else ""))
        L.append(f"- 멈춘 자리: {loc['stop']['name']}")
    if res.get("hypotheses"):
        L += ["", "**원인 가설(근거 순)**"]
        L += [f"{h['rank']}. {h['name']} — {h['where']} · 근거 {h['strength']} · {h['why']} → {h['todo']}" for h in res["hypotheses"]]
    order = {"bad": 0, "warn": 1, "ok": 2, "na": 3}
    L += ["", "| 상태 | 자리 | 질문 | 대상 | 근거 | 할 일 |", "|---|---|---|---|---|---|"]
    for c in sorted(res["checks"], key=lambda c: (order[c["status"]], c["node"])):
        L.append(f"| {c['status_name']} | {c['where']} | {c['q']} | {c['target'] or ''} | {c['evidence']} | {c['todo']} |")
    L += ["", "**연결 상태**"] + [f"- {'연결됨' if s['on'] else '없음'} · {s['name']} ({s['how']})" for s in res["sources"]]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--weekly", action="store_true")
    ap.add_argument("--advertiser", default="")
    a = ap.parse_args()
    run = Path(a.run)
    data = Data(run, d(a.date))
    res = {"advertiser": a.advertiser or run.parent.name, "date": a.date, "rhythm": "weekly" if a.weekly else "daily"}
    if a.weekly:
        w = run_weekly(data)
        res.update({"checks": w["checks"], "hypotheses": w["hypotheses"], "weeks": w["weeks"], "factors": w.get("factors"), "signal": None, "location": None})
    else:
        res.update(run_daily(data))
    res["nodes"] = node_status(res["checks"])
    res["sources"] = [{"file": f, "name": n, "how": h, "unlocks": u, "on": connected(run, f)} for f, n, h, u in SOURCES]
    save(run, "result.json", res)
    (run / "report.md").write_text(report(res), encoding="utf-8")
    cnt = {s: sum(1 for c in res["checks"] if c["status"] == s) for s in STATUS_NAME}
    print(f"점검 {len(res['checks'])}개 — " + " · ".join(f"{STATUS_NAME[s]} {n}" for s, n in cnt.items()) + f" → {run / 'report.md'}")


if __name__ == "__main__":
    main()
