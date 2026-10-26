"""데일리 점검 — 같아야 할 값이 그대로인가."""
from datetime import date, timedelta
from pathlib import Path

from lib import (BASE_DAYS, CROWD_SHARE, MIN_EVENTS, SPREAD_RATE, SPREAD_SHARE, check, days_before, decompose,
                 load, pct, ratio, roas, total, usual_range, won)

LEVELS = ["account", "campaign", "adset", "ad"]
PARENT_KEY = {"campaign": "account_id", "adset": "campaign_id", "ad": "adset_id"}
LEVEL_NAME = {"account": "계정", "campaign": "캠페인", "adset": "광고세트", "ad": "광고"}


class Data:
    def __init__(self, run: Path, target: date):
        self.run, self.target, self.t = run, target, target.isoformat()
        self.base = [x.isoformat() for x in days_before(target, BASE_DAYS)]
        self.ins = load(run, "insights.json", []) or []
        self.meta = load(run, "meta.json")
        self.prev = self._prev_snapshot()
        self.acts = load(run, "activities.json")
        self.web = load(run, "web.json")
        self.site = load(run, "site.json")
        self.peers = load(run, "peers.json")
        self.pixel = load(run, "pixel.json")
        self.names = {}
        if self.meta:
            for k in ("campaigns", "adsets", "ads"):
                for o in self.meta.get(k, []):
                    self.names[o["id"]] = o.get("name", o["id"])

    def _prev_snapshot(self):
        snaps = self.run.parent / "snapshots"
        if not snaps.exists():
            return None
        older = sorted(p for p in snaps.glob("*.json") if p.stem < self.t)
        return load(snaps, older[-1].name) if older else None

    def rows(self, level):
        got = [r for r in self.ins if r.get("level") == level]
        if got or level == "ad":
            return got
        out = {}  # 위 단계 행이 없으면 광고 행을 묶는다
        for r in self.rows("ad"):
            key = (r.get(f"{level}_id") or r.get("account_id") or "acct", r["date"])
            o = out.setdefault(key, {"level": level, "id": key[0], "date": key[1], "account_id": r.get("account_id"),
                                     "campaign_id": r.get("campaign_id"), "adset_id": r.get("adset_id"), "name": r.get(f"{level}_name") or ""})
            for m in ("spend", "impressions", "clicks", "lpv", "view_content", "add_to_cart", "initiate_checkout", "purchases", "revenue"):
                o[m] = o.get(m, 0) + float(r.get(m) or 0)
        return list(out.values())

    def actor(self, object_id):
        for e in reversed(self.acts or []):
            if e.get("object_id") == object_id and str(e.get("event_time", "")).startswith(self.t):
                return f"{e.get('actor_name') or '누군가'} · {str(e.get('event_time'))[11:16]} · {e.get('translated_event_type') or e.get('event_type')}"
        return None


def unit_stats(rows, uid, d: Data):
    mine = [r for r in rows if r["id"] == uid]
    now = total([r for r in mine if r["date"] == d.t])
    base = total([r for r in mine if r["date"] in d.base])
    days = len({r["date"] for r in mine if r["date"] in d.base}) or 1
    rb, rn = roas(base), roas(now)
    lost = now["spend"] * (rb - rn) if rb is not None and rn is not None else 0.0
    rate = (1 - rn / rb) if rb and rn is not None else None
    return {"id": uid, "name": d.names.get(uid) or next((r.get("name") for r in mine if r.get("name")), uid),
            "now": now, "base_daily_spend": base["spend"] / days, "roas_now": rn, "roas_base": rb, "lost": lost, "rate": rate}


def locate(d: Data):
    trail, parent_level = [], "account"
    acct_rows = d.rows("account")
    if not acct_rows:
        return {"trail": [], "stop": None, "note": "성과 데이터가 없다"}
    parent = unit_stats(acct_rows, acct_rows[0]["id"], d)
    parent["level"] = "account"
    for child_level in LEVELS[1:]:
        rows = d.rows(child_level)
        key = PARENT_KEY[child_level]
        ids = sorted({r["id"] for r in rows if child_level == "campaign" or r.get(key) == parent["id"]})
        kids = [unit_stats(rows, i, d) for i in ids]
        kids = [k for k in kids if k["now"]["spend"] > 0 or k["base_daily_spend"] > 0]
        if parent["lost"] <= 0 or not kids:
            trail.append({"level": parent_level, "unit": slim(parent), "decision": "하락 없음" if parent["lost"] <= 0 else "아래 단계 데이터 없음 — 한 단계 아래를 내보내 이어 본다", "children": []})
            return {"trail": trail, "stop": {"level": parent_level, **slim(parent)}}
        pos = sum(max(k["lost"], 0) for k in kids) or 1
        for k in kids:
            k["share"] = max(k["lost"], 0) / pos
        kids.sort(key=lambda k: -k["lost"])
        spend_all = sum(k["now"]["spend"] for k in kids) or 1
        pr = parent["rate"] or 0
        together = sum(k["now"]["spend"] for k in kids if k["rate"] is not None and pr > 0 and k["rate"] >= SPREAD_RATE * pr) / spend_all
        top = kids[0]
        if len(kids) == 1:
            decision = "몰림"
        elif together >= SPREAD_SHARE:
            decision = "퍼짐"
        elif top["share"] >= CROWD_SHARE:
            decision = "몰림"
        else:
            decision = "보류"
        trail.append({"level": parent_level, "unit": slim(parent), "decision": decision, "together": together,
                      "children": [dict(slim(k), level=child_level) for k in kids[:6]]})
        if decision != "몰림":
            return {"trail": trail, "stop": {"level": parent_level, **slim(parent)}}
        parent, parent_level = top, child_level
    trail.append({"level": parent_level, "unit": slim(parent), "decision": "가장 아래", "children": []})
    return {"trail": trail, "stop": {"level": parent_level, **slim(parent)}}


def slim(u):
    return {k: u.get(k) for k in ("id", "name", "roas_now", "roas_base", "lost", "rate", "share")} | {"spend": u["now"]["spend"] if "now" in u else u.get("spend")}


def signal(d: Data):
    acct = d.rows("account")
    days = {}
    for r in acct:
        days.setdefault(r["date"], []).append(r)
    daily = {k: total(v) for k, v in days.items()}
    now = daily.get(d.t)
    base = total([daily[x] for x in d.base if x in daily])
    if not now:
        return None
    usual = usual_range([roas(daily[x]) for x in d.base if x in daily])
    return {"roas_now": roas(now), "roas_base": roas(base), "usual": usual, "now": now, "base": base,
            "base_days": sum(1 for x in d.base if x in daily), "factors": decompose(now, base), "daily": daily}


def ratio_check(node, q, num, den, sig, d, todo, label):
    """'평소 범위' 판정: 대상일 비율이 앞 기간 하루하루의 범위 아래인가."""
    if not sig:
        return check(node, q, "na", "성과 데이터 없음", basis="평소 범위")
    now = sig["now"]
    if now[den] < MIN_EVENTS:
        return check(node, q, "warn", f"{label}: 표본이 작다({now[den]:.0f}건)", "표본이 쌓인 뒤 다시 본다", basis="평소 범위")
    v = ratio(now[num], now[den])
    usual = usual_range([ratio(sig["daily"][x][num], sig["daily"][x][den]) for x in d.base if x in sig["daily"] and sig["daily"][x][den] >= MIN_EVENTS / 2])
    if not usual:
        return check(node, q, "warn", f"{label} {pct(v, 1)} — 평소 범위가 아직 없다(기록 부족)", "값만 보고 화면으로 확인한다", basis="평소 범위")
    ev = f"{label} {pct(v, 1)} · 평소 {pct(usual['min'], 1)}~{pct(usual['max'], 1)}"
    if v < usual["min"]:
        return check(node, q, "bad", ev + " → 평소보다 낮다", todo, basis="평소 범위", urgency="당일")
    return check(node, q, "ok", ev, basis="평소 범위")


def run_daily(d: Data):
    out = []
    sig = signal(d)

    # ── 신호판
    if not sig:
        out.append(check("G", "정말 떨어졌나?", "na", f"{d.t} 성과가 없다"))
    else:
        u = sig["usual"]
        ev = f"어제 ROAS {pct(sig['roas_now'])} · 앞 {sig['base_days']}일 합계 {pct(sig['roas_base'])}"
        late = d.target >= date.today() - timedelta(days=1)
        if not u:
            out.append(check("G", "정말 떨어졌나?", "warn", ev + " · 평소 범위 없음", "기록이 쌓일 때까지 앞 기간 합계와만 비교한다", basis="평소 범위"))
        elif sig["roas_now"] is not None and sig["roas_now"] < u["min"]:
            out.append(check("G", "정말 떨어졌나?", "bad", ev + f" · 평소 하루 최저 {pct(u['min'])}보다 낮다" + (" · 전환이 늦게 잡히는 중일 수 있다" if late else ""),
                             "원인 자리 찾기로 간다", basis="평소 범위", urgency="당일"))
        else:
            out.append(check("G", "정말 떨어졌나?", "ok", ev + f" · 평소 범위 {pct(u['min'])}~{pct(u['max'])} 안", basis="평소 범위"))

    # 업종 · 자사몰 비교
    if d.peers:
        dropped, n = 0, 0
        for name in sorted({p["name"] for p in d.peers}):
            mine = {p["date"]: p["roas"] for p in d.peers if p["name"] == name}
            ur = usual_range([mine.get(x) for x in d.base])
            if ur and mine.get(d.t) is not None:
                n += 1
                dropped += mine[d.t] < ur["min"]
        if n:
            st = "bad" if dropped / n >= 0.6 else "ok"
            out.append(check("S4", "같은 업종도 어제 같이 떨어졌나?", st, f"같은 업종 {n}곳 중 {dropped}곳 하락",
                             "시장 · 플랫폼 원인으로 보고 우리 계정만의 문제부터 걸러 낸다", basis="몰렸나 · 퍼졌나", urgency="관찰"))
    site_daily = {r["date"]: r for r in (d.site or {}).get("daily", [])}
    if sig and site_daily.get(d.t):
        base_site = [site_daily[x]["revenue"] for x in d.base if x in site_daily]
        if base_site:
            s_chg = site_daily[d.t]["revenue"] / (sum(base_site) / len(base_site)) - 1
            base_meta = sig["base"]["revenue"] / max(sig["base_days"], 1)
            m_chg = sig["now"]["revenue"] / base_meta - 1 if base_meta else None
            both = m_chg is not None and m_chg < 0 and s_chg <= m_chg * 0.6
            out.append(check("G", "자사몰 전체도 떨어졌나?", "warn" if both else "ok",
                             f"자사몰 매출 {pct(s_chg)} · 메타 기여 매출 {pct(m_chg)} (앞 기간 하루 평균 대비)",
                             "자사 웹 상태부터 본다", basis="몰렸나 · 퍼졌나"))

    # ── 시장(데일리는 달력 · 플랫폼만)
    special = (d.site or {}).get("special_days")
    if special is not None:
        hit = [s for s in special if s.get("date") == d.t]
        out.append(check("S1", "오늘이 평소와 다른 날인가?", "warn" if hit else "ok",
                         ", ".join(s.get("name", "") for s in hit) or "평소와 같은 날", "비교하는 날을 같은 성격의 날로 바꾼다", basis="늘 맞아야 함"))
    out.append(check("S5", "메타에 장애 · 지연이 있나?", "na", "자동으로 보지 않는다", basis="늘 맞아야 함"))

    out += media_checks(d, sig)
    out += web_checks(d, sig)
    return {"signal": slim_signal(sig), "location": locate(d) if sig else None, "checks": out}


def slim_signal(sig):
    if not sig:
        return None
    return {k: sig[k] for k in ("roas_now", "roas_base", "usual", "base_days", "factors")} | {
        "spend_now": sig["now"]["spend"], "revenue_now": sig["now"]["revenue"]}


def media_checks(d: Data, sig):
    out = []
    if not d.meta:
        return [check(n, "설정 스냅샷", "na", "meta.json 없음") for n in ("M1", "M2", "M3", "M4")]
    acc = d.meta.get("account", {})
    st = acc.get("account_status")
    out.append(check("M1", "계정이 살아 있나?", "ok" if str(st) == "1" else "bad", f"계정 상태 {st}" + (f" · 사유 {acc.get('disable_reason')}" if str(st) != "1" else ""),
                     "바로 광고주 · 메타에 문의한다", basis="늘 맞아야 함", urgency="즉시"))
    if d.acts is not None:
        declines = [e for e in d.acts if e.get("event_type") in ("ad_account_billing_decline", "remove_funding_source") and str(e.get("event_time", ""))[:10] >= (d.target - timedelta(days=1)).isoformat()]
        out.append(check("M1", "결제가 됐나?", "bad" if declines else "ok", f"결제 실패 · 결제 수단 제거 {len(declines)}건",
                         "결제 수단을 확인한다", basis="늘 맞아야 함", urgency="즉시"))
    cap = float(acc.get("spend_cap") or 0)
    if cap and sig:
        unit = 1 if acc.get("currency") in ("KRW", "JPY") else 100
        left = (cap - float(acc.get("amount_spent") or 0)) / unit
        daily = sig["base"]["spend"] / max(sig["base_days"], 1)
        out.append(check("M1", "내일도 돌 수 있나?", "bad" if left < daily else "ok", f"남은 한도 {won(left)} · 하루 평균 소진 {won(daily)}",
                         "한도 증액을 요청한다", basis="늘 맞아야 함", urgency="당일"))

    promos = (d.site or {}).get("promos", [])
    camp_spend = {}
    for r in d.rows("campaign"):
        if r["date"] == d.t:
            camp_spend[r["id"]] = camp_spend.get(r["id"], 0) + r["spend"]
    on_off_bad = 0
    for c in d.meta.get("campaigns", []):
        active = c.get("effective_status") == "ACTIVE"
        for p in promos:
            if p.get("match") and p["match"] in c.get("name", ""):
                ended, running = d.t > p["end"], p["start"] <= d.t <= p["end"]
                if active and ended:
                    on_off_bad += 1
                    out.append(check("M2", "켜질 때 켜지고 꺼질 때 꺼졌나?", "bad", f"'{p['name']}' {p['end']} 종료 · 아직 켜짐",
                                     "끄거나 상시 랜딩으로 바꾸고, 광고주에게 연장 여부를 확인한다", target=c["name"], basis="늘 맞아야 함", urgency="즉시"))
                elif running and not active:
                    on_off_bad += 1
                    out.append(check("M2", "켜질 때 켜지고 꺼질 때 꺼졌나?", "bad", f"'{p['name']}' 진행 중 · 꺼져 있음 ({c.get('effective_status')})",
                                     "켜고 누가 껐는지 확인한다", target=c["name"], basis="늘 맞아야 함", urgency="즉시"))
        if active and camp_spend.get(c["id"], 0) == 0 and c["id"] in camp_spend:
            out.append(check("M2", "켜져 있는데 돈이 안 쓰이나?", "bad", "켜져 있는데 어제 소진 0", "반려 · 한도 · 일정 중 무엇이 막았는지 본다",
                             target=c["name"], basis="늘 맞아야 함", urgency="당일"))
    if promos and not on_off_bad:
        out.append(check("M2", "켜질 때 켜지고 꺼질 때 꺼졌나?", "ok", f"행사 {len(promos)}건과 캠페인 상태가 맞다", basis="늘 맞아야 함"))

    for ad in d.meta.get("ads", []):
        if ad.get("issues") or ad.get("effective_status") in ("DISAPPROVED", "WITH_ISSUES"):
            out.append(check("M4", "반려 · 제한됐나?", "bad", f"{ad.get('effective_status')} · {'; '.join(i for i in ad.get('issues') or [] if i)}",
                             "소재를 고쳐 다시 심사받는다", target=ad.get("name", ad["id"]), basis="늘 맞아야 함", urgency="당일"))
    if not any(c["node"] == "M4" and c["q"].startswith("반려") for c in out):
        out.append(check("M4", "반려 · 제한됐나?", "ok", "반려 · 제한 없음", basis="늘 맞아야 함"))
    if sig:
        ad_base = {}
        for r in d.rows("ad"):
            if r["date"] in d.base:
                ad_base[r["id"]] = ad_base.get(r["id"], 0) + r["revenue"]
        top = sorted(ad_base, key=lambda k: -ad_base[k])[:5]
        status = {a["id"]: a.get("effective_status") for a in d.meta.get("ads", [])}
        off = [a for a in top if status.get(a) and status[a] != "ACTIVE"]
        for a in off:
            who = d.actor(a)
            out.append(check("M4", "잘 되던 광고가 꺼졌나?", "bad", f"앞 기간 매출 상위 소재 · 지금 {status[a]}" + (f" · {who}" if who else ""),
                             "누가 껐는지 보고 다시 켤지 정한다", target=d.names.get(a, a), basis="늘 맞아야 함", urgency="당일"))
        if not off:
            out.append(check("M4", "잘 되던 광고가 꺼졌나?", "ok", f"매출 상위 소재 {len(top)}개 모두 켜짐", basis="늘 맞아야 함"))

    out += diff_checks(d)
    return out


DIFF_FIELDS = {
    "campaigns": ("M2", [("daily_budget", "예산 · 한도가 바뀌었나?"), ("lifetime_budget", "예산 · 한도가 바뀌었나?"), ("spend_cap", "예산 · 한도가 바뀌었나?"), ("objective", "목표가 바뀌었나?")]),
    "adsets": ("M3", [("daily_budget", "예산 · 입찰이 바뀌었나?"), ("lifetime_budget", "예산 · 입찰이 바뀌었나?"), ("bid_strategy", "예산 · 입찰이 바뀌었나?"),
                      ("bid_amount", "예산 · 입찰이 바뀌었나?"), ("optimization_goal", "무엇을 목표로 돌고 있나?"), ("promoted_object", "무엇을 목표로 돌고 있나?"),
                      ("attribution_spec", "성과를 세는 방식이 바뀌었나?"), ("excluded_audiences", "타겟 · 제외가 그대로인가?"), ("custom_audiences", "타겟 · 제외가 그대로인가?")]),
    "ads": ("M4", [("link_url", "연결 주소가 바뀌었나?")]),
}


def diff_checks(d: Data):
    if not d.prev:
        return [check(n, "어제와 같나?", "na", "앞선 스냅샷이 없다 — 다음 실행부터 비교된다", basis="어제와 같나") for n in ("M2", "M3", "M4")]
    out = []
    for kind, (node, fields) in DIFF_FIELDS.items():
        before = {o["id"]: o for o in d.prev.get(kind, [])}
        changed = 0
        for o in d.meta.get(kind, []):
            p = before.get(o["id"])
            if not p:
                continue
            for f, q in fields:
                if (o.get(f) or None) != (p.get(f) or None):
                    changed += 1
                    who = d.actor(o["id"])
                    out.append(check(node, q, "warn", f"{FIELD_KO.get(f, f)}: {short(p.get(f))} → {short(o.get(f))}" + (f" · {who}" if who else " · 변경 이력에 없음"),
                                     "의도한 변경인지 확인한다", target=o.get("name", o["id"]), basis="어제와 같나"))
            if kind == "adsets" and p.get("learning_status") == "SUCCESS" and o.get("learning_status") == "LEARNING":
                changed += 1
                out.append(check("M3", "학습이 다시 시작됐나?", "warn", "학습 완료 → 학습 중", "추가 변경을 멈추고 지켜본다", target=o.get("name", o["id"]), basis="어제와 같나"))
        if not changed:
            out.append(check(node, "어제와 같나?", "ok", f"앞선 스냅샷({d.prev.get('taken_for')})과 설정이 같다", basis="어제와 같나"))
    return out


FIELD_KO = {"daily_budget": "일예산", "lifetime_budget": "총예산", "spend_cap": "지출 한도", "objective": "목표", "bid_strategy": "입찰 방식",
            "bid_amount": "입찰가", "optimization_goal": "최적화 이벤트", "promoted_object": "최적화 대상", "attribution_spec": "기여 설정",
            "excluded_audiences": "제외 오디언스", "custom_audiences": "포함 오디언스", "link_url": "연결 주소"}


def short(v):
    if isinstance(v, str) and v.isdigit():
        return f"{int(v):,}"
    s = str(v)
    return s if len(s) <= 40 else s[:37] + "…"


def web_checks(d: Data, sig):
    out = []
    if sig:
        out.append(ratio_check("J1", "클릭한 사람이 페이지까지 오나?", "lpv", "clicks", sig, d, "페이지가 늦게 뜨거나 막힌다. 랜딩 속도부터 본다", "랜딩 조회 ÷ 링크 클릭"))
        out.append(ratio_check("J4", "장바구니에 담기나?", "add_to_cart", "view_content", sig, d, "담기 버튼 · 옵션 오류, 또는 상품 · 행사 상태를 확인한다", "장바구니 ÷ 상품 조회"))
        out.append(ratio_check("J5", "결제가 되나?", "purchases", "initiate_checkout", sig, d, "결제 오류. 광고주에게 바로 알리고 결제 수단별로 확인한다", "구매 ÷ 결제 시작"))
    site_daily = {r["date"]: r for r in (d.site or {}).get("daily", [])}
    if sig and site_daily.get(d.t):
        orders, mp = site_daily[d.t].get("orders", 0), sig["now"]["purchases"]
        if orders > 0 and mp == 0:
            out.append(check("J6", "구매가 잡히나?", "bad", f"자사몰 주문 {orders} · 메타 구매 0", "측정 복구를 요청한다. 예산 · 소재는 건드리지 않는다", basis="늘 맞아야 함", urgency="즉시"))
        else:
            vals = [ratio(sig["daily"][x]["purchases"], site_daily[x]["orders"]) for x in d.base if x in sig["daily"] and x in site_daily and site_daily[x].get("orders")]
            ur, v = usual_range(vals), ratio(mp, orders)
            if ur and v is not None and v < ur["min"]:
                out.append(check("J6", "구매가 잡히나?", "warn", f"메타 구매 ÷ 자사몰 주문 {pct(v)} · 평소 {pct(ur['min'])}~{pct(ur['max'])} — 측정이 샜거나, 메타 성과만 떨어졌다",
                                 "결제 단계 비율이 평소 범위면 측정보다 성과 하락으로 본다. 둘 다 낮으면 측정 점검을 요청한다", basis="평소 범위"))
            else:
                out.append(check("J6", "구매가 잡히나?", "ok" if ur else "warn", f"메타 구매 {mp:.0f} · 자사몰 주문 {orders}" + ("" if ur else " · 평소 범위 없음"), "값만 보고 확인한다", basis="평소 범위"))
    if d.pixel:
        per_day = {}
        for p in d.pixel:
            if p.get("event") == "Purchase":
                day = str(p.get("hour", ""))[:10]
                per_day[day] = per_day.get(day, 0) + int(p.get("count") or 0)
        others = [v for k, v in per_day.items() if k != d.t]
        now = per_day.get(d.t, 0)
        st = "bad" if others and now < min(others) * 0.5 else "ok" if others else "warn"
        out.append(check("JT", "이벤트 수가 그대로인가?", st, f"어제 구매 이벤트 {now} · 최근 다른 날 {min(others) if others else '—'}~{max(others) if others else '—'}",
                         "태그 · 사이트 변경을 확인한다", basis="평소 범위", urgency="당일"))

    w = d.web
    if not w:
        return out + [check("J1", "광고 주소가 열리나?", "na", "web.json 없음 — web_check.py를 돌린다", basis="늘 맞아야 함")]
    if w.get("home"):
        h = w["home"]
        out.append(check("J1", "사이트가 살아 있나?", "ok" if h.get("status") == 200 else "bad", f"첫 화면 응답 {h.get('status')} · {h.get('ms')}ms",
                         "사이트 장애. 광고주에게 바로 알리고 메타 광고 전체 일시 중지를 검토한다", basis="늘 맞아야 함", urgency="즉시"))
    url_ads = {}
    for ad in (d.meta or {}).get("ads", []):
        if ad.get("link_url"):
            url_ads.setdefault(ad["link_url"], []).append(ad.get("name", ad["id"]))
    seen = {"soldout": 0, "ended": 0, "tag": 0, "params": 0, "home": 0, "slow": 0}
    for p in w.get("pages", []):
        tgt = p["url"] + (f" (광고 {len(url_ads.get(p['url'], []))}개)" if url_ads.get(p["url"]) else "")
        if p.get("status") != 200:
            out.append(check("J1", "광고 주소가 열리나?", "bad", f"응답 {p.get('status')} {p.get('error') or ''}".strip(), "그 주소로 보내는 광고를 끄거나 주소를 바꾸고 광고주에게 알린다",
                             target=tgt, basis="늘 맞아야 함", urgency="즉시"))
            continue
        out.append(check("J1", "광고 주소가 열리나?", "ok", f"응답 200 · {len(p.get('chain', []))}번 이동", target=tgt, basis="늘 맞아야 함"))
        if p.get("went_home"):
            seen["home"] += 1
            out.append(check("J1", "엉뚱한 곳으로 가나?", "bad", f"첫 화면으로 이동: {p.get('final_url')}", "광고의 연결 주소나 사이트 이동 설정을 고친다", target=tgt, basis="늘 맞아야 함", urgency="당일"))
        if not (p.get("kept_utm") and p.get("kept_fbclid")):
            seen["params"] += 1
            out.append(check("J1", "꼬리표가 남나?", "bad", f"UTM {'유지' if p.get('kept_utm') else '사라짐'} · fbclid {'유지' if p.get('kept_fbclid') else '사라짐'}",
                             "사이트 이동 설정 수정을 요청한다(성과가 메타로 안 잡힌다)", target=tgt, basis="늘 맞아야 함", urgency="당일"))
        ended = p.get("ended_words") or []
        promo_end = [x for x in (d.site or {}).get("promos", []) if x.get("url") == p["url"] and d.t > x["end"]]
        if ended or promo_end:
            seen["ended"] += 1
            why = (f"페이지에 '{ended[0]}' 표시" if ended else "") + (f" · '{promo_end[0]['name']}' {promo_end[0]['end']} 종료" if promo_end else "")
            out.append(check("J2", "행사가 아직 하나?", "bad", why.strip(" ·"), "광고를 끄거나 상시 페이지로 바꾼다", target=tgt, basis="늘 맞아야 함", urgency="즉시"))
        if p.get("soldout_words"):
            seen["soldout"] += 1
            out.append(check("J3", "살 수 있나?", "warn", f"페이지에 '{p['soldout_words'][0]}' 표시 — 다른 상품 표시일 수 있다", "화면으로 주력 상품 · 옵션 품절인지 확인한다", target=tgt, basis="늘 맞아야 함"))
        if (p.get("ms") or 0) > 3000:
            seen["slow"] += 1
            out.append(check("J2", "빨리 뜨나?", "warn", f"페이지 받는 데 {p['ms']}ms · 평소 범위 없음", "화면으로 로딩을 확인한다", target=tgt, basis="평소 범위"))
        if not (p.get("has_pixel") or p.get("has_gtm")):
            seen["tag"] += 1
            out.append(check("JT", "이벤트가 나가나?", "warn", "페이지 원본에 픽셀 · GTM 흔적이 없다(다른 방식으로 심었을 수 있다)", "브라우저로 이벤트 발동을 확인한다", target=tgt, basis="늘 맞아야 함"))
    n = len([p for p in w.get("pages", []) if p.get("status") == 200])
    if n:
        oks = [("J1", "엉뚱한 곳으로 가나?", "home", "첫 화면으로 튕기는 주소 없음"), ("J1", "꼬리표가 남나?", "params", "UTM · fbclid 모두 유지"),
               ("J2", "행사가 아직 하나?", "ended", "종료 표시 · 끝난 행사 주소 없음"), ("J2", "빨리 뜨나?", "slow", "모두 3초 안에 받음"),
               ("J3", "살 수 있나?", "soldout", "페이지 글에 품절 표시 없음"), ("JT", "이벤트가 나가나?", "tag", "모든 주소에 픽셀 · GTM 흔적 있음(실제 발동은 브라우저로 확인)")]
        for node, q, k, ev in oks:
            if not seen[k]:
                out.append(check(node, q, "ok", f"{ev} · 주소 {n}개", basis="늘 맞아야 함"))
    return out
