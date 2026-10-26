"""ROAS 점검 공통 도우미 — 실행 폴더 읽기, 합계, 판정 결과 형식."""
import json
import math
from datetime import date, timedelta
from pathlib import Path

# 알고리즘 매개변수(표준값이 아니라 판정 방식의 손잡이). 학습 회로에서 고친다.
BASE_DAYS = 14          # 데일리 비교 기간: 대상일 앞 14일
MIN_BASE_DAYS = 7       # '평소 범위'를 만들 최소 일수
MIN_EVENTS = 20         # 비율 판정에 필요한 최소 분모(이보다 작으면 확인 필요)
CROWD_SHARE = 0.5       # 몰림: 잃은 매출 몫이 이 이상인 하위 단위가 있음
SPREAD_SHARE = 0.7      # 퍼짐: 광고비 기준으로 이만큼의 하위 단위가 같이 떨어짐
SPREAD_RATE = 0.5       # 같이 떨어짐 = 하락률이 상위 하락률의 이 배수 이상
STREAK_TOL = 0.02       # 몇 주째: 이보다 작은 흔들림은 하락으로 세지 않는다

STATUS_ORDER = {"bad": 3, "warn": 2, "ok": 1, "na": 0}
STATUS_NAME = {"bad": "이상", "warn": "확인 필요", "ok": "정상", "na": "못 봄"}

NODE_NAME = {
    "G": "신호판",
    "S1": "시장 › 달력 · 시즌", "S2": "시장 › 수요", "S3": "시장 › 경매 · 경쟁", "S4": "시장 › 업종 흐름", "S5": "시장 › 플랫폼",
    "J1": "자사 › 도착", "J2": "자사 › 랜딩", "J3": "자사 › 상품", "J4": "자사 › 장바구니", "J5": "자사 › 결제", "J6": "자사 › 구매 완료", "JT": "자사 › 측정 태그",
    "M1": "매체 › 계정", "M2": "매체 › 캠페인", "M3": "매체 › 광고세트", "M4": "매체 › 광고(소재)", "MX": "매체 › 단면",
}

METRICS = ["spend", "impressions", "clicks", "lpv", "view_content", "add_to_cart", "initiate_checkout", "purchases", "revenue"]


def load(run: Path, name: str, default=None):
    p = run / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(run: Path, name: str, obj):
    (run / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def d(s: str) -> date:
    return date.fromisoformat(s[:10])


def days_before(target: date, n: int):
    return [target - timedelta(days=k) for k in range(n, 0, -1)]


def total(rows, keys=METRICS):
    out = {k: 0.0 for k in keys}
    for r in rows:
        for k in keys:
            out[k] += float(r.get(k) or 0)
    return out


def ratio(a, b):
    return a / b if b else None


def roas(t):
    return ratio(t["revenue"], t["spend"])


def factors(t):
    """ROAS = 클릭률 × 구매 전환율 × 객단가 ÷ 노출 단가."""
    return {
        "cpm": ratio(t["spend"] * 1000, t["impressions"]),
        "ctr": ratio(t["clicks"], t["impressions"]),
        "cvr": ratio(t["purchases"], t["clicks"]),
        "aov": ratio(t["revenue"], t["purchases"]),
    }


def decompose(now, base):
    """ln ROAS 변화를 네 숫자의 몫으로 나눈다. 노출 단가는 부호를 뒤집는다."""
    fn, fb = factors(now), factors(base)
    parts = {}
    for k in ["cpm", "ctr", "cvr", "aov"]:
        if not fn[k] or not fb[k]:
            parts[k] = None
            continue
        v = math.log(fn[k] / fb[k])
        parts[k] = -v if k == "cpm" else v
    tot = sum(abs(v) for v in parts.values() if v is not None) or 1
    return {k: {"now": fn[k], "base": fb[k], "change": (fn[k] / fb[k] - 1) if fn[k] and fb[k] else None,
                "effect": v, "share": (abs(v) / tot if v is not None else None)} for k, v in parts.items()}


def by_day(rows, key=None, value=None):
    """날짜별로 묶어 합계. key/value로 단위를 거른다."""
    out = {}
    for r in rows:
        if key and r.get(key) != value:
            continue
        out.setdefault(r["date"], []).append(r)
    return {k: total(v) for k, v in out.items()}


def usual_range(values):
    vals = [v for v in values if v is not None]
    if len(vals) < MIN_BASE_DAYS:
        return None
    vals.sort()
    return {"min": vals[0], "max": vals[-1], "mid": vals[len(vals) // 2], "n": len(vals)}


def check(node, q, status, evidence, todo="", target="", basis="", urgency=""):
    return {"node": node, "where": NODE_NAME.get(node, node), "target": target, "q": q,
            "status": status, "status_name": STATUS_NAME[status], "evidence": evidence,
            "todo": todo if status in ("bad", "warn") else "", "basis": basis, "urgency": urgency if status == "bad" else ""}


def pct(x, digits=0):
    return "—" if x is None else f"{x * 100:.{digits}f}%"


def won(x):
    return "—" if x is None else f"{x:,.0f}"
