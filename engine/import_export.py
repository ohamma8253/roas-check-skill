"""광고 관리자 내보내기(CSV)를 점검용 insights.json으로 바꾼다.

  python3 import_export.py --run RUN_DIR --level campaign 캠페인_일별.csv [--level ad 광고_일별.csv ...]

내보낼 때: 분석 데이터 › 시간 › 일(하루 단위), 기간은 점검일 포함 앞 14일 이상(위클리는 5주).
열 이름은 한국어 · 영어 화면 모두 받는다. 못 알아본 열은 끝에 알려 준다.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import save  # noqa: E402

COLS = {  # 표준 이름: 열 이름에 들어 있으면 그 열로 본다(앞에 있을수록 우선)
    "date": ["일", "보고 시작", "Day", "Reporting starts"],
    "campaign_name": ["캠페인 이름", "Campaign name"],
    "adset_name": ["광고 세트 이름", "Ad set name"],
    "ad_name": ["광고 이름", "Ad name"],
    "campaign_id": ["캠페인 ID", "Campaign ID"],
    "adset_id": ["광고 세트 ID", "Ad set ID"],
    "ad_id": ["광고 ID", "Ad ID"],
    "spend": ["지출 금액", "Amount spent"],
    "impressions": ["노출", "Impressions"],
    "reach": ["도달", "Reach"],
    "frequency": ["빈도", "Frequency"],
    "clicks": ["링크 클릭", "Link clicks"],
    "lpv": ["랜딩 페이지 조회", "Landing page views"],
    "view_content": ["콘텐츠 조회", "Content views"],
    "add_to_cart": ["장바구니에 담기", "Adds to cart"],
    "initiate_checkout": ["결제 시작", "Checkouts initiated"],
    "revenue": ["구매 전환값", "Purchases conversion value", "Purchase conversion value"],
    "purchases": ["구매", "Purchases"],
}
SKIP_IN = {"clicks": ["링크 클릭당", "Cost per", "CTR", "클릭률"], "purchases": ["전환값", "conversion value", "당 비용", "Cost per", "ROAS"],
           "impressions": ["당 비용", "CPM"], "lpv": ["당 비용", "Cost per"], "view_content": ["당 비용", "Cost per"],
           "add_to_cart": ["당 비용", "Cost per"], "initiate_checkout": ["당 비용", "Cost per"], "reach": ["당 비용", "Cost per"]}


def map_headers(headers):
    used, out = set(), {}
    for key, names in COLS.items():
        for h in headers:
            if h in used:
                continue
            if any(n.lower() in h.lower() for n in names) and not any(s.lower() in h.lower() for s in SKIP_IN.get(key, [])):
                out[key] = h
                used.add(h)
                break
    return out, [h for h in headers if h not in used]


def num(v):
    v = (v or "").replace(",", "").replace("₩", "").replace("%", "").strip()
    try:
        return float(v)
    except ValueError:
        return 0.0


def read(path, level):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return [], [], {}
    m, unknown = map_headers(list(rows[0].keys()))
    if "date" not in m:
        raise SystemExit(f"{path}: 날짜 열이 없다. 내보낼 때 '분석 데이터 › 시간 › 일'을 고른다.")
    out = []
    for r in rows:
        x = {k: r.get(h, "") for k, h in m.items()}
        row = {"level": level, "date": x["date"][:10]}
        for k in ("campaign_name", "adset_name", "ad_name", "campaign_id", "adset_id", "ad_id"):
            row[k] = x.get(k) or None
        for k in ("spend", "impressions", "reach", "frequency", "clicks", "lpv", "view_content", "add_to_cart", "initiate_checkout", "purchases", "revenue"):
            row[k] = num(x.get(k))
        for lv in ("campaign", "adset", "ad"):  # ID가 없으면 이름을 ID로 쓴다
            row[f"{lv}_id"] = row[f"{lv}_id"] or row[f"{lv}_name"]
        row["id"] = row.get(f"{level}_id") or "account"
        row["name"] = row.get(f"{level}_name") or "계정"
        row["account_id"] = "account"
        out.append(row)
    return out, unknown, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--level", action="append", nargs=2, metavar=("LEVEL", "CSV"), required=True,
                    help="account|campaign|adset|ad 와 CSV 경로")
    a = ap.parse_args()
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    allrows = []
    for level, path in a.level:
        rows, unknown, m = read(path, level)
        allrows += rows
        print(f"{level}: {len(rows)}행 · 알아본 열 {', '.join(m)}" + (f" · 못 알아본 열 {len(unknown)}개" if unknown else ""))
        missing = [k for k in ("spend", "impressions", "clicks", "purchases", "revenue") if k not in m]
        if missing:
            print(f"  빠진 열: {', '.join(missing)} — 열 설정에 추가해 다시 내보낸다")
    if not any(r["level"] == "account" for r in allrows):  # 계정 합계는 가장 위 단계 행을 날짜별로 더해 만든다
        top = next((lv for lv in ("campaign", "adset", "ad") if any(r["level"] == lv for r in allrows)), None)
        acc = {}
        for r in (x for x in allrows if x["level"] == top):
            o = acc.setdefault(r["date"], {"level": "account", "date": r["date"], "id": "account", "name": "계정", "account_id": "account"})
            for k in ("spend", "impressions", "clicks", "lpv", "view_content", "add_to_cart", "initiate_checkout", "purchases", "revenue"):
                o[k] = o.get(k, 0) + r[k]
        allrows += list(acc.values())
    save(run, "insights.json", allrows)
    print(f"→ {run / 'insights.json'}")


if __name__ == "__main__":
    main()
