"""위클리 점검 — 흐름이 어디서 꺾였나. 판정은 순위 · 방향으로만 한다."""
import json
from datetime import date

from lib import STREAK_TOL, check, decompose, load, pct, ratio, roas, total

WEEKS = 5  # 이번 주 + 앞 4주
FACTOR_NAME = {"cpm": "노출 단가", "ctr": "클릭률", "cvr": "구매 전환율", "aov": "객단가"}


def week_of(d, day):
    k = (d.target - date.fromisoformat(day)).days // 7
    return k if 0 <= k < WEEKS else None


def weekly_totals(rows, d, exclude=()):
    out = [[] for _ in range(WEEKS)]
    for r in rows:
        if r["date"] in exclude:
            continue
        k = week_of(d, r["date"])
        if k is not None:
            out[k].append(r)
    return [total(w) for w in out]


def streak(values, lower_is_bad=True):
    """이번 주부터 거꾸로, 몇 주째 나빠지는 방향인가. values[0] = 이번 주."""
    n = 0
    for k in range(len(values) - 1):
        a, b = values[k], values[k + 1]
        if a is None or b is None:
            break
        if (a < b * (1 - STREAK_TOL)) if lower_is_bad else (a > b * (1 + STREAK_TOL)):
            n += 1
        else:
            break
    return n


def incidents(d):
    """같은 광고주의 데일리 실행에서 '이상'이 있던 날."""
    days = set()
    for res in d.run.parent.glob("*/result.json"):
        try:
            r = json.loads(res.read_text(encoding="utf-8"))
        except Exception:
            continue
        if r.get("rhythm") == "daily" and any(c["status"] == "bad" and c["node"] != "G" for c in r.get("checks", [])):
            days.add(r.get("date"))
    return days


def mix_rate(units_now, units_base):
    """ROAS 변화 = 비중 이동 몫 + 각자 변화 몫."""
    sn = sum(u["spend"] for u in units_now.values()) or 1
    sb = sum(u["spend"] for u in units_base.values()) or 1
    mix = rate = 0.0
    for k in set(units_now) | set(units_base):
        n, b = units_now.get(k), units_base.get(k)
        wn, wb = (n["spend"] / sn if n else 0), (b["spend"] / sb if b else 0)
        rn, rb = (roas(n) if n else None), (roas(b) if b else None)
        if rb is not None:
            mix += (wn - wb) * rb
        if rn is not None and rb is not None:
            rate += wn * (rn - rb)
    tot = abs(mix) + abs(rate) or 1
    return {"mix": mix, "rate": rate, "mix_share": abs(mix) / tot}


def units(rows, d, week_ks, level_key="id"):
    out = {}
    for r in rows:
        k = week_of(d, r["date"])
        if k in week_ks:
            out.setdefault(r[level_key], []).append(r)
    return {k: total(v) for k, v in out.items()}


def run_weekly(d):
    out, flags = [], {}
    acct = d.rows("account")
    if not acct:
        return {"checks": [check("G", "몇 주째인가?", "na", "성과 데이터 없음")], "hypotheses": [], "weeks": []}
    inc = incidents(d)
    weeks = weekly_totals(acct, d)
    have = [w for w in weeks if w["spend"] > 0]
    if len(have) < 3:
        return {"checks": [check("G", "몇 주째인가?", "warn", f"주 단위 데이터 {len(have)}주 — 3주 이상 필요", "--weekly로 5주치를 받는다", basis="몇 주째")], "hypotheses": [], "weeks": []}
    r = [roas(w) for w in weeks]
    s = streak(r)
    out.append(check("G", "몇 주째인가?", "bad" if s >= 2 else "warn" if s == 1 else "ok",
                     "주별 ROAS(이번 주부터): " + " · ".join(pct(x) for x in r), "원인 읽기로 간다", basis="몇 주째"))
    if inc:
        wx = weekly_totals(acct, d, exclude=inc)
        out.append(check("G", "급한 사고를 빼도 떨어졌나?", "bad" if roas(wx[0]) and roas(wx[1]) and roas(wx[0]) < roas(wx[1]) else "ok",
                         f"사고 난 날 {', '.join(sorted(inc))} 빼고 이번 주 {pct(roas(wx[0]))} · 지난주 {pct(roas(wx[1]))}", "방향 문제로 본다", basis="어느 숫자가"))
    base = total(weeks[1:])
    dec = decompose(weeks[0], base)
    worst = min((k for k in dec if dec[k]["effect"] is not None), key=lambda k: dec[k]["effect"], default=None)
    out.append(check("G", "어느 숫자가 얼마나 끌어내렸나?", "bad" if worst and dec[worst]["effect"] < 0 else "ok",
                     " | ".join(f"{FACTOR_NAME[k]} {pct(v['change'], 1)}" for k, v in dec.items()) + (f" ← {FACTOR_NAME[worst]} 몫이 가장 크다" if worst else ""),
                     "그 숫자에서 원인 읽기를 시작한다", basis="어느 숫자가"))

    # 비중 이동: 캠페인 사이
    camp = d.rows("campaign")
    mr = mix_rate(units(camp, d, {0}), units(camp, d, {1, 2, 3, 4}))
    flags["mix"] = mr["mix_share"] >= 0.5 and mr["mix"] < 0
    out.append(check("M1", "효율 낮은 캠페인으로 돈이 옮겨 갔나?", "bad" if flags["mix"] else "ok",
                     f"ROAS 변화 중 비중 이동 몫 {pct(mr['mix_share'])}", "캠페인 예산을 다시 나눈다", basis="비중 이동"))

    # 단계 비율의 흐름
    steps = [("J1", "클릭한 사람이 페이지까지 오나?", "lpv", "clicks"), ("J4", "장바구니에 담기나?", "add_to_cart", "view_content"),
             ("J5", "어느 단계가 계속 나빠지나?", "purchases", "initiate_checkout")]
    for node, q, num, den in steps:
        vals = [ratio(w[num], w[den]) for w in weeks]
        n = streak(vals)
        flags[f"step_{node}"] = n >= 2
        out.append(check(node, q, "bad" if n >= 2 else "ok", f"{num}÷{den} 주별: " + " · ".join(pct(v, 1) for v in vals) + f" · {n}주째 하락",
                         "그 단계 개선을 제안한다", basis="몇 주째"))

    # 측정이 새나
    site = {x["date"]: x for x in (d.site or {}).get("daily", [])}
    if site:
        orders = [0.0] * WEEKS
        for day, x in site.items():
            k = week_of(d, day)
            if k is not None:
                orders[k] += x.get("orders", 0)
        vals = [ratio(weeks[k]["purchases"], orders[k]) for k in range(WEEKS)]
        n = streak(vals)
        out.append(check("J6", "측정이 조금씩 새나?", "bad" if n >= 2 else "ok", "메타 구매 ÷ 자사몰 주문 주별: " + " · ".join(pct(v) for v in vals), "측정 점검을 요청한다", basis="몇 주째"))

    # 소재 · 타겟 (주 단위 성과가 있으면 빈도까지)
    wk = load(d.run, "insights_weekly.json")
    ad_rows = [x for x in (wk or d.rows("ad")) if x.get("level") == "ad"]
    by_ad = {}
    for x in ad_rows:
        k = week_of(d, x["date"]) if not wk else (d.target - date.fromisoformat(x.get("date_end") or x["date"])).days // 7
        if k is not None and 0 <= k < WEEKS:
            by_ad.setdefault(x["id"], {}).setdefault(k, []).append(x)
    spend0 = {a: sum(r["spend"] for r in w.get(0, [])) for a, w in by_ad.items()}
    worn = []
    for a in sorted(spend0, key=lambda a: -spend0[a])[:5]:
        w = by_ad[a]
        ctr = [ratio(sum(r["clicks"] for r in w.get(k, [])), sum(r["impressions"] for r in w.get(k, []))) for k in range(WEEKS)]
        freq = [sum(r.get("frequency", 0) * r["impressions"] for r in w.get(k, [])) / (sum(r["impressions"] for r in w.get(k, [])) or 1) for k in range(WEEKS)] if wk else None
        down = streak(ctr)
        up = streak(freq, lower_is_bad=False) if freq else None
        if down >= 2 and (up is None or up >= 1):
            worn.append(a)
            out.append(check("M4", "소재가 닳았나?", "bad", f"클릭률 {down}주째 하락: " + " · ".join(pct(v, 2) for v in ctr) + (f" · 빈도 {up}주째 상승" if up else " · 빈도는 주 단위 성과가 있어야 본다"),
                             "새 소재를 넣고 닳은 소재 비중을 줄인다", target=d.names.get(a, a), basis="닳았나"))
    flags["worn"] = bool(worn)
    if not worn and by_ad:
        out.append(check("M4", "소재가 닳았나?", "ok", "지출 상위 소재에서 이어지는 클릭률 하락 없음", basis="닳았나"))

    if wk:
        narrow = []
        sets = {}
        for x in wk:
            if x.get("level") == "adset":
                k = (d.target - date.fromisoformat(x.get("date_end") or x["date"])).days // 7
                if 0 <= k < 2:
                    sets.setdefault(x["id"], {})[k] = x
        for a, w in sets.items():
            if 0 in w and 1 in w and w[1]["spend"] > 0 and w[1]["reach"] > 0:
                ds, dr = w[0]["spend"] / w[1]["spend"] - 1, w[0]["reach"] / w[1]["reach"] - 1
                if ds > 0 and dr <= ds / 3 and w[0].get("frequency", 0) > w[1].get("frequency", 0):
                    narrow.append(a)
                    out.append(check("M3", "타겟이 좁아졌나?", "bad", f"광고비 {pct(ds)} · 도달 {pct(dr)} · 빈도 {w[1].get('frequency', 0):.1f} → {w[0].get('frequency', 0):.1f}",
                                     "유사 타겟을 넓히고 리타겟 범위를 조정한다", target=d.names.get(a, a), basis="같이 움직임"))
        flags["narrow"] = bool(narrow)
    for n, q in (("S2", "찾는 사람이 줄었나?"), ("S3", "광고 자리가 비싸졌나?"), ("S4", "업종 흐름과 같은 방향인가?")):
        out.append(check(n, q, "na", "검색 수요 · 업종 묶음 데이터가 연결되지 않았다", basis="몇 주째"))
    return {"checks": out, "hypotheses": hypotheses(dec, flags), "weeks": [{"roas": roas(w), "spend": w["spend"]} for w in weeks], "factors": dec}


def hypotheses(dec, flags):
    """같이 움직인 숫자로 원인 가설을 세우고 근거 수로 순위를 매긴다."""
    eff = {k: (v["effect"] or 0) for k, v in dec.items()}
    hs = []

    def add(name, where, score, why, todo):
        hs.append({"name": name, "where": where, "score": score, "why": why, "todo": todo})

    if eff["ctr"] < 0:
        add("소재가 닳았다", "매체 › 광고(소재) · 단면(소구점)", -eff["ctr"] + (0.3 if flags.get("worn") else 0),
            "클릭률이 내려갔다" + (" · 지출 상위 소재가 이어서 닳는다" if flags.get("worn") else ""), "새 소구점 테스트, 닳은 소재 비중 축소")
    if eff["cpm"] < 0:
        add("자리가 비싸졌다 / 타겟이 좁다", "시장 › 경매 · 경쟁 · 매체 › 광고세트", -eff["cpm"] + (0.3 if flags.get("narrow") else 0),
            "노출 단가가 올랐다" + (" · 광고비는 느는데 도달이 그대로인 광고세트가 있다" if flags.get("narrow") else ""), "효율 단위로 모으기 · 유사 타겟 확대")
    if eff["cvr"] < 0:
        blocked = [k for k in ("step_J1", "step_J4", "step_J5") if flags.get(k)]
        add("사이트에서 막히거나 설득을 못 한다", "자사 › 랜딩 · 장바구니 · 결제", -eff["cvr"] + 0.2 * len(blocked),
            "구매 전환율이 내려갔다" + (f" · 몇 주째 나빠지는 단계 {len(blocked)}곳" if blocked else ""), "막힌 단계 확인 · 랜딩 메시지 · 혜택 협의")
    if eff["aov"] < 0:
        add("싼 상품으로 쏠렸다", "자사 › 상품", -eff["aov"], "객단가가 내려갔다", "주력 상품 · 세트 노출 조정")
    if flags.get("mix"):
        add("돈이 낮은 데로 옮겨 갔다", "매체 › 계정 · 캠페인", 0.4, "ROAS 변화의 절반 이상이 비중 이동", "효율 캠페인 예산 보장")
    hs.sort(key=lambda h: -h["score"])
    for k, h in enumerate(hs):
        h["rank"] = k + 1
        h["strength"] = "강함" if h["score"] >= 0.3 else "보통" if h["score"] >= 0.1 else "약함"
    return hs
