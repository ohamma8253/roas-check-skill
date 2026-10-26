"""예시 실행 폴더 만들기 — 'A사(예시)' 가을 행사 캠페인이 끝난 뒤에도 켜져 있는 사례. 모든 숫자는 지어낸 것.

  python3 make_sample.py --out RUNS_DIR   → RUNS_DIR/A사(예시)/2026-10-22-daily/
"""
import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import save  # noqa: E402

TARGET = date(2026, 10, 22)
SHOP = "https://shop.example.com"
SETS = [  # 광고세트, 캠페인, 하루 광고비, 평소 ROAS, 어제 ROAS 배수, 연결 주소
    ("A-1", "A", 600_000, 3.95, 0.90, "/product/stretch-pants"),
    ("A-2", "A", 600_000, 3.85, 0.92, "/product/knit-cardigan"),
    ("B-1 · 신규", "B", 1_100_000, 4.20, 0.45, "/event/fall-sale"),
    ("B-2 · 관심사", "B", 900_000, 4.00, 0.46, "/event/fall-sale"),
    ("C-1", "C", 800_000, 3.30, 0.88, "/product/stretch-pants"),
]
CAMPS = {"A": "캠페인 A · 상시", "B": "캠페인 B · 가을 행사", "C": "캠페인 C · 리타겟"}


def day_row(level, rid, name, camp, aset, ad, day, spend, roas, rnd, wear=1.0):
    spend *= rnd.uniform(0.95, 1.05)
    rev = spend * roas * rnd.uniform(0.96, 1.04)
    imp = spend / 8000 * 1000
    clicks = imp * 0.012 * wear
    lpv = clicks * 0.86
    vc = lpv * 0.92
    purchases = rev / 62_000
    ic = purchases / 0.62
    atc = ic / 0.48
    return {"level": level, "id": rid, "name": name, "date": day, "account_id": "act_example", "campaign_id": camp, "adset_id": aset, "ad_id": ad,
            "spend": round(spend), "impressions": round(imp), "reach": round(imp / 1.7), "frequency": 1.7, "clicks": round(clicks), "lpv": round(lpv),
            "view_content": round(vc), "add_to_cart": round(atc), "initiate_checkout": round(ic), "purchases": round(purchases), "revenue": round(rev)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--days", type=int, default=14, help="앞 기간 일수(위클리 시험은 35)")
    a = ap.parse_args()
    adv = Path(a.out) / "A사(예시)"
    run = adv / f"{TARGET.isoformat()}-daily"
    run.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(7)
    rows = []
    days = [TARGET - timedelta(days=k) for k in range(a.days, -1, -1)]
    for day in days:
        ds = day.isoformat()
        for i, (sid, cid, spend, roas, mult, path) in enumerate(SETS):
            r = roas * (mult if day == TARGET else 1)
            weeks_ago = (TARGET - day).days // 7
            wear = 1 - 0.07 * (4 - min(weeks_ago, 4)) if cid == "A" and a.days >= 28 else 1  # 위클리 시험에서만 A 소재가 닳는다
            r *= wear
            ad = day_row("ad", f"ad{i}", f"{sid} 소재", cid, sid, f"ad{i}", ds, spend, r, rnd, wear)
            rows.append(ad)
            rows.append(dict(ad, level="adset", id=sid, name=sid))
    for lv, key in (("campaign", "campaign_id"), ("account", "account_id")):
        agg = {}
        for r in [x for x in rows if x["level"] == "adset"]:
            k = (r[key], r["date"])
            o = agg.setdefault(k, {"level": lv, "id": r[key], "name": CAMPS.get(r[key], "계정"), "date": r["date"], "account_id": "act_example",
                                   "campaign_id": r["campaign_id"] if lv == "campaign" else None})
            for m in ("spend", "impressions", "reach", "clicks", "lpv", "view_content", "add_to_cart", "initiate_checkout", "purchases", "revenue"):
                o[m] = o.get(m, 0) + r[m]
        rows += list(agg.values())
    save(run, "insights.json", rows)

    snap = {
        "taken_for": TARGET.isoformat(),
        "account": {"id": "act_example", "name": "A사(예시)", "account_status": 1, "currency": "KRW", "spend_cap": "0", "amount_spent": "0"},
        "campaigns": [{"id": c, "name": n, "effective_status": "ACTIVE", "objective": "OUTCOME_SALES", "daily_budget": None} for c, n in CAMPS.items()],
        "adsets": [{"id": s[0], "name": s[0], "campaign_id": s[1], "effective_status": "ACTIVE", "daily_budget": str(s[2]), "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                    "optimization_goal": "OFFSITE_CONVERSIONS", "promoted_object": {"custom_event_type": "PURCHASE"}, "attribution_spec": [{"event_type": "CLICK_THROUGH", "window_days": 7}],
                    "excluded_audiences": ["구매자_180일"], "custom_audiences": [], "learning_status": "SUCCESS"} for s in SETS],
        "ads": [{"id": f"ad{i}", "name": f"{s[0]} 소재", "adset_id": s[0], "campaign_id": s[1], "effective_status": "ACTIVE", "issues": [], "link_url": SHOP + s[5]} for i, s in enumerate(SETS)],
    }
    save(run, "meta.json", snap)
    prev = __import__("copy").deepcopy(snap)
    prev["taken_for"] = (TARGET - timedelta(days=1)).isoformat()
    prev["adsets"][0]["daily_budget"] = "500000"
    snaps = adv / "snapshots"
    snaps.mkdir(exist_ok=True)
    save(snaps, f"{prev['taken_for']}.json", prev)
    save(snaps, f"{TARGET.isoformat()}.json", snap)
    save(run, "activities.json", [{"event_type": "update_ad_set_budget", "translated_event_type": "광고 세트 예산 수정", "event_time": f"{TARGET.isoformat()}T10:12:00+0900",
                                   "actor_name": "운영 담당자", "object_id": "A-1", "object_name": "A-1"}])

    web = {"ua": "mobile", "home": {"url": SHOP, "status": 200, "final_url": SHOP, "chain": [], "ms": 640},
           "pages": []}
    for path in sorted({s[5] for s in SETS}):
        ended = path == "/event/fall-sale"
        web["pages"].append({"url": SHOP + path, "status": 200, "final_url": SHOP + path + "?utm_source=roascheck&fbclid=roascheck", "chain": [], "ms": 900 if not ended else 1200,
                             "kept_utm": True, "kept_fbclid": True, "went_home": False, "soldout_words": [], "ended_words": ["종료된 이벤트"] if ended else [],
                             "has_pixel": True, "has_gtm": True, "title": "가을 행사" if ended else "상품"})
    save(run, "web.json", web)

    meta_rev = {}
    for r in rows:
        if r["level"] == "account":
            meta_rev[r["date"]] = r["revenue"]
    daily = []
    for day in days:
        ds = day.isoformat()
        rev = meta_rev[ds] * 1.6 if day != TARGET else meta_rev[(TARGET - timedelta(days=1)).isoformat()] * 1.6 * 0.92
        daily.append({"date": ds, "revenue": round(rev), "orders": round(rev / 62_000)})
    save(run, "site.json", {"daily": daily, "special_days": [],
                            "promos": [{"name": "가을 행사", "match": "가을", "start": "2026-10-14", "end": "2026-10-21", "url": SHOP + "/event/fall-sale"}]})
    peers = []
    for n in ("업종 1", "업종 2", "업종 3", "업종 4"):
        base = rnd.uniform(2.8, 4.2)
        for day in days:
            peers.append({"name": n, "date": day.isoformat(), "roas": round(base * rnd.uniform(0.93, 1.07), 3)})
    save(run, "peers.json", peers)
    print(run)


if __name__ == "__main__":
    main()
