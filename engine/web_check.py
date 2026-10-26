"""자사 웹 상태 점검기 — 광고 연결 주소를 휴대폰처럼 열어 본다.

  python3 web_check.py --run RUN_DIR [--url URL ...] [--home https://shop.example.com] [--inapp]

주소는 --url, 없으면 RUN_DIR/meta.json의 광고 연결 주소(켜진 광고)를 쓴다. 결과는 RUN_DIR/web.json.
보는 것: 응답 코드 · 이동 경로 · UTM/fbclid 유지 · 받는 데 걸린 시간 · 품절/종료 표시 · 픽셀/GTM 흔적.
화면 깨짐 · 이벤트 실제 발동 · 결제 앱 전환은 이 점검기로 못 본다(브라우저로 따로 확인).
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import load, save  # noqa: E402

UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
UA_INAPP = UA_MOBILE + " Instagram 330.0.0.0 (iPhone; iOS 17_5; ko_KR)"
SOLDOUT = ["품절", "일시품절", "sold out", "soldout", "재입고 알림"]
ENDED = ["종료된 이벤트", "이벤트가 종료", "기획전이 종료", "판매 종료", "판매종료", "종료되었습니다", "마감되었습니다"]
TEST_UTM = "roascheck"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def with_test_params(url):
    p = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    q = [(k, v) for k, v in q if k not in ("utm_source", "fbclid")] + [("utm_source", TEST_UTM), ("fbclid", TEST_UTM)]
    return urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode(q)))


def fetch(url, ua, max_hops=8):
    chain, cur, t0 = [], url, time.time()
    for _ in range(max_hops):
        req = urllib.request.Request(cur, headers={"User-Agent": ua, "Accept-Language": "ko-KR,ko;q=0.9"})
        try:
            r = OPENER.open(req, timeout=30)
            body = r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "replace")
            return {"status": r.status, "final_url": cur, "chain": chain, "ms": int((time.time() - t0) * 1000), "body": body}
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                nxt = urllib.parse.urljoin(cur, e.headers["Location"])
                chain.append({"status": e.code, "to": nxt})
                cur = nxt
                continue
            return {"status": e.code, "final_url": cur, "chain": chain, "ms": int((time.time() - t0) * 1000), "body": ""}
        except Exception as e:  # 연결 실패 · 시간 초과
            return {"status": None, "final_url": cur, "chain": chain, "ms": int((time.time() - t0) * 1000), "body": "", "error": str(e)[:200]}
    return {"status": None, "final_url": cur, "chain": chain, "ms": int((time.time() - t0) * 1000), "body": "", "error": "리다이렉트 반복"}


def visible_text(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", html))


def inspect(url, ua):
    r = fetch(with_test_params(url), ua)
    body, text = r.pop("body"), ""
    if body:
        text = visible_text(body).lower()
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(r["final_url"]).query))
    orig_path = urllib.parse.urlsplit(url).path.rstrip("/")
    final_path = urllib.parse.urlsplit(r["final_url"]).path.rstrip("/")
    return {
        "url": url, **r,
        "kept_utm": q.get("utm_source") == TEST_UTM, "kept_fbclid": q.get("fbclid") == TEST_UTM,
        "went_home": bool(orig_path) and final_path == "" and bool(r["chain"]),
        "soldout_words": [w for w in SOLDOUT if w in text],
        "ended_words": [w for w in ENDED if w in text],
        "has_pixel": ("fbevents.js" in body) or ("fbq(" in body),
        "has_gtm": "googletagmanager.com/gtm.js" in body or "gtm.js?id=" in body,
        "title": (re.search(r"(?is)<title[^>]*>(.*?)</title>", body or "") or [None, ""])[1].strip()[:120],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--home", help="사이트 첫 화면 주소(사이트 전체가 살아 있는지 본다)")
    ap.add_argument("--inapp", action="store_true", help="인스타그램 앱 안 브라우저처럼 연다")
    a = ap.parse_args()
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    urls = list(a.url)
    if not urls:
        meta = load(run, "meta.json", {}) or {}
        urls = sorted({ad["link_url"] for ad in meta.get("ads", []) if ad.get("link_url") and ad.get("effective_status") == "ACTIVE"})
    if not urls:
        raise SystemExit("점검할 주소가 없다. --url로 넘기거나 meta.json을 먼저 만든다.")
    ua = UA_INAPP if a.inapp else UA_MOBILE
    out = {"ua": "inapp" if a.inapp else "mobile", "home": None, "pages": []}
    if a.home:
        out["home"] = inspect(a.home, ua)
    for u in urls:
        out["pages"].append(inspect(u, ua))
        time.sleep(0.5)
    save(run, "web.json", out)
    bad = [p for p in out["pages"] if p["status"] != 200]
    print(f"웹 점검: {len(urls)}개 주소, 응답 이상 {len(bad)}개 → {run / 'web.json'}")


if __name__ == "__main__":
    main()
