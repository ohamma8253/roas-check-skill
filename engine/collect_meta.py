"""메타 마케팅 API(읽기 전용)에서 점검용 데이터를 모아 실행 폴더에 정리한다.

토큰은 환경변수 META_ACCESS_TOKEN으로만 받는다(파일에서 읽지 않는다, 출력하지 않는다).

  python3 collect_meta.py --account act_123 --date 2026-10-22 --out RUN_DIR [--weekly] [--pixel 456]

만드는 파일: meta.json(설정 스냅샷) · insights.json · activities.json · pixel.json · insights_weekly.json(--weekly)
스냅샷은 RUN_DIR/../snapshots/<날짜>.json에도 남겨 다음 실행의 '어제와 같나' 기준이 된다.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import BASE_DAYS, d, save  # noqa: E402

API = "https://graph.facebook.com"

ACTION_KEYS = {  # 앞에 있는 이름이 있으면 그것을 쓴다
    "lpv": ["landing_page_view", "omni_landing_page_view"],
    "view_content": ["omni_view_content", "view_content", "offsite_conversion.fb_pixel_view_content"],
    "add_to_cart": ["omni_add_to_cart", "add_to_cart", "offsite_conversion.fb_pixel_add_to_cart"],
    "initiate_checkout": ["omni_initiated_checkout", "initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout"],
    "purchases": ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase"],
}


class Meta:
    def __init__(self, token, version):
        self.token, self.version = token, version

    def get(self, path, params=None):
        params = dict(params or {})
        params["access_token"] = self.token
        url = f"{API}/{self.version}/{path}?{urllib.parse.urlencode(params)}"
        return self._fetch(url)

    def _fetch(self, url):
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in (429, 500, 503) and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise SystemExit(f"메타 API 오류 {e.code}: {body[:300]}")
        raise SystemExit("메타 API 응답 없음")

    def all(self, path, params=None):
        page = self.get(path, params)
        rows = list(page.get("data", []))
        while page.get("paging", {}).get("next"):
            page = self._fetch(page["paging"]["next"])
            rows += page.get("data", [])
        return rows


def pick(actions, keys):
    found = {a["action_type"]: float(a.get("value", 0)) for a in actions or []}
    for k in keys:
        if k in found:
            return found[k]
    return 0.0


def norm_insight(r, level):
    acts, vals = r.get("actions"), r.get("action_values")
    row = {
        "level": level, "date": r.get("date_start"), "date_end": r.get("date_stop"),
        "account_id": r.get("account_id"), "campaign_id": r.get("campaign_id"), "campaign_name": r.get("campaign_name"),
        "adset_id": r.get("adset_id"), "adset_name": r.get("adset_name"), "ad_id": r.get("ad_id"), "ad_name": r.get("ad_name"),
        "spend": float(r.get("spend") or 0), "impressions": float(r.get("impressions") or 0),
        "reach": float(r.get("reach") or 0), "frequency": float(r.get("frequency") or 0),
        "clicks": float(r.get("inline_link_clicks") or 0),
        "revenue": pick(vals, ACTION_KEYS["purchases"]),
    }
    for k, keys in ACTION_KEYS.items():
        row[k] = pick(acts, keys)
    row["id"] = row.get(f"{level}_id") or row.get("account_id")
    row["name"] = row.get(f"{level}_name") or ""
    return row


def link_of(creative):
    spec = (creative or {}).get("object_story_spec") or {}
    for k in ("link_data", "video_data"):
        v = spec.get(k) or {}
        if v.get("link"):
            return v["link"]
        cta = (v.get("call_to_action") or {}).get("value") or {}
        if cta.get("link"):
            return cta["link"]
    feed = (creative or {}).get("asset_feed_spec") or {}
    urls = feed.get("link_urls") or []
    return urls[0].get("website_url") if urls else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="act_로 시작하는 광고 계정 ID")
    ap.add_argument("--date", required=True, help="점검 대상일(보통 어제) YYYY-MM-DD")
    ap.add_argument("--out", required=True)
    ap.add_argument("--weekly", action="store_true", help="위클리용 주 단위 성과(최근 5주)도 받는다")
    ap.add_argument("--pixel", help="픽셀(데이터셋) ID — 있으면 이벤트 수를 받는다")
    ap.add_argument("--version", default="v25.0")
    a = ap.parse_args()

    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise SystemExit("META_ACCESS_TOKEN 환경변수가 없다. 토큰을 환경변수로 넘기거나, 광고 관리자 내보내기 파일로 진행한다(references/data-contract.md).")
    acc = a.account if a.account.startswith("act_") else f"act_{a.account}"
    m = Meta(token, a.version)
    run = Path(a.out)
    run.mkdir(parents=True, exist_ok=True)
    target = d(a.date)
    since = target - timedelta(days=(35 if a.weekly else BASE_DAYS))

    account = m.get(acc, {"fields": "id,name,account_status,disable_reason,spend_cap,amount_spent,currency,timezone_name"})
    campaigns = m.all(f"{acc}/campaigns", {"fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,spend_cap,start_time,stop_time", "limit": 500})
    adsets = m.all(f"{acc}/adsets", {"fields": "id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,budget_remaining,bid_strategy,bid_amount,optimization_goal,promoted_object,attribution_spec,targeting,learning_stage_info,start_time,end_time", "limit": 500})
    ads = m.all(f"{acc}/ads", {"fields": "id,name,adset_id,campaign_id,status,effective_status,issues_info,created_time,creative{object_story_spec,asset_feed_spec}", "limit": 500})
    for s in adsets:
        t = s.pop("targeting", {}) or {}
        s["excluded_audiences"] = sorted(x.get("id") for x in t.get("excluded_custom_audiences", []) or [])
        s["custom_audiences"] = sorted(x.get("id") for x in t.get("custom_audiences", []) or [])
        s["learning_status"] = (s.pop("learning_stage_info", {}) or {}).get("status")
    for ad in ads:
        ad["link_url"] = link_of(ad.pop("creative", None))
        ad["issues"] = [i.get("error_summary") or i.get("error_message") for i in ad.pop("issues_info", []) or []]
    snap = {"account": account, "campaigns": campaigns, "adsets": adsets, "ads": ads, "taken_for": a.date}
    save(run, "meta.json", snap)
    snaps = run.parent / "snapshots"
    snaps.mkdir(exist_ok=True)
    save(snaps, f"{a.date}.json", snap)

    fields = "account_id,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,reach,frequency,inline_link_clicks,actions,action_values"
    tr = json.dumps({"since": since.isoformat(), "until": a.date})
    rows = []
    for level in ("account", "campaign", "adset", "ad"):
        got = m.all(f"{acc}/insights", {"level": level, "time_increment": 1, "time_range": tr, "fields": fields, "limit": 500})
        rows += [norm_insight(r, level) for r in got]
    save(run, "insights.json", rows)

    if a.weekly:
        wrows = []
        for level in ("account", "campaign", "adset", "ad"):
            got = m.all(f"{acc}/insights", {"level": level, "time_increment": 7, "time_range": tr, "fields": fields, "limit": 500})
            wrows += [norm_insight(r, level) for r in got]
        save(run, "insights_weekly.json", wrows)

    acts = m.all(f"{acc}/activities", {"since": since.isoformat(), "until": (target + timedelta(days=1)).isoformat(),
                                       "fields": "event_type,event_time,actor_name,object_id,object_name,object_type,extra_data", "limit": 500})
    save(run, "activities.json", acts)

    if a.pixel:  # 최근 7일까지만 조회된다
        p_since = max(since, target - timedelta(days=6))
        stats = []
        for src in ("WEB_ONLY", "SERVER_ONLY"):
            got = m.all(f"{a.pixel}/stats", {"aggregation": "event", "event_source": src, "start_time": p_since.isoformat(), "end_time": (target + timedelta(days=1)).isoformat()})
            for g in got:
                for e in g.get("data", []):
                    stats.append({"hour": g.get("start_time"), "event": e.get("value"), "count": e.get("count"), "source": src})
        save(run, "pixel.json", stats)

    print(f"모음: 캠페인 {len(campaigns)} · 광고세트 {len(adsets)} · 광고 {len(ads)} · 성과 {len(rows)}행 · 변경 {len(acts)}건 → {run}")


if __name__ == "__main__":
    main()
