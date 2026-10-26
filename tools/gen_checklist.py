"""html/data.js · html/checks.js(정본) → 스킬의 references/checklist.md"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "skill" / "roas-check" / "references" / "checklist.md"

SCREEN = {  # 사용자에게 안내할 화면 위치(메뉴 이름은 메타 화면 버전에 따라 조금 다를 수 있다)
    "G": "광고 관리자 › 캠페인 탭 › 기간 '어제', 비교 '앞 14일'(위클리는 주 단위) › 열: 지출 금액 · 노출 · CPM · 링크 클릭 · CTR(링크 클릭률) · 구매 · 구매 전환값 · 구매 ROAS. 자사몰 관리자의 일별 매출.",
    "S1": "광고주 행사 달력, 공휴일 · 쇼핑 대목 달력",
    "S2": "네이버 데이터랩 검색어 트렌드, 구글 트렌드(카테고리 · 브랜드 검색어)",
    "S3": "광고 관리자 CPM 주별 추이, 메타 광고 라이브러리에서 경쟁 브랜드 검색",
    "S4": "직접 운영하는 같은 업종 광고주 계정의 같은 기간 ROAS · CPM",
    "S5": "메타 비즈니스 상태 페이지, 비즈니스 지원 홈 공지",
    "J1": "광고 수정 화면 또는 미리보기의 웹사이트 URL을 휴대폰으로 열기 · 광고 관리자 열: 링크 클릭 · 랜딩 페이지 조회",
    "J2": "같은 주소를 휴대폰 브라우저와 인스타그램 앱(광고 미리보기 링크)에서 열어 첫 화면 · 속도 · 행사 표시 보기",
    "J3": "상품 페이지(재고 · 옵션 · 가격 · 쿠폰), 커머스 관리자 › 카탈로그 진단",
    "J4": "광고 관리자 열: 콘텐츠 조회 · 장바구니에 담기 / 휴대폰으로 직접 담아 보기",
    "J5": "광고 관리자 열: 결제 시작 · 구매 / 결제 직전 화면까지 직접 진행(실제 결제는 하지 않는다)",
    "J6": "자사몰 관리자 주문 수 vs 광고 관리자 구매 수 · 이벤트 관리자에서 구매 이벤트 금액 · 분석 데이터 › 게재 › 기기(한 기기만 구매가 사라졌나)",
    "JT": "이벤트 관리자 › 데이터 세트 › 개요(이벤트별 수 · 브라우저/서버) · 테스트 이벤트 · GTM 버전 기록",
    "M1": "광고 관리자 › 결제 및 청구(결제 설정 · 지출 한도), 계정 품질, 대상(맞춤 오디언스), 활동 기록(변경 내역)",
    "M2": "캠페인 탭 › 게재 상태 · 예산 · 일정 · 목표, 캠페인 선택 › 기록(변경 내역)",
    "M3": "광고세트 탭 › 게재(학습 단계) · 예산 · 입찰 · 최적화 이벤트 · 기여 설정 · 타겟(제외 대상 포함)",
    "M4": "광고 탭 › 게재 상태 · 반려 사유, 광고 수정 › 웹사이트 URL, 열: 빈도 · 품질 순위 · 참여율 순위 · 전환율 순위",
    "MX": "분석 데이터 › 게재 › 노출 위치 · 기기 · 연령 · 성별 / 소재 이름 · 태그로 소구점 묶기",
}


def js_value(path, var):
    s = path.read_text(encoding="utf-8")
    body = s[s.index("=") + 1:].strip().rstrip(";")
    body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
    body = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', body)  # 키에 따옴표
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def main():
    data = js_value(ROOT / "html" / "data.js", "ROAS_DATA")
    checks = js_value(ROOT / "html" / "checks.js", "ROAS_CHECKS")
    basis = data["basis"]
    nodes = [("G", "신호판", "무엇이 떨어졌나 → 어디부터 볼까", None)]
    for L in data["layers"]:
        for n in L["nodes"]:
            nodes.append((n["id"], f"{L['name']}({L['lens']}) › {n['name']}", n["hint"], L))
        for extra in ("rail", "cross"):
            if L.get(extra):
                n = L[extra]
                nodes.append((n["id"], f"{L['name']}({L['lens']}) › {n['name']}", n["hint"], L))
    out = ["# ROAS 저하 점검 체크리스트", "",
           "정본: 점검 지도(html/checks.js)에서 자동 생성. 자리마다 데일리(같아야 할 값) · 위클리(흐름)로 나눈다.",
           "'화면'은 사용자에게 안내할 위치다. 메뉴 이름은 메타 화면 버전에 따라 조금 다를 수 있다. 단계 카드(SKILL.md)가 묶어 묻지 않은 항목은 필요할 때 여기서 꺼낸다.", "",
           "## 신호판 — 어느 숫자가 어디를 가리키나", "", "| 숫자 | 방향 | 뜻 | 어디부터 |", "|---|---|---|---|"]
    out += [f"| {t['k']} | {t['dir']} | {t['why']} | {t['to']} |" for t in data["tiles"]]
    out += ["", "## 판정 기준", ""] + [f"- **{b['name']}** ({'데일리' if b['r'] == 'D' else '위클리'}) — {b['desc']}" for b in basis.values()]
    for nid, title, hint, L in nodes:
        mine = [c for c in checks if c[0] == nid]
        if not mine:
            continue
        out += ["", f"## {title}", f"_{hint}_" + (f" · 여기가 원인이면: {L['shape']}" if L else ""), "", f"**화면** {SCREEN.get(nid, '')}"]
        for r, rname in (("D", "데일리"), ("W", "위클리")):
            rows = [c for c in mine if c[1] == r]
            if not rows:
                continue
            out += ["", f"### {rname}"]
            for c in rows:
                flag = " *(메타 필드 이름 확인 필요)*" if len(c) > 7 and c[7] else ""
                out.append(f"- **{c[2]}** `{basis[c[6]]['name']}`{flag}  \n  보는 곳: {c[3]}  \n  이상 신호: {c[4]}  \n  할 일: {c[5]}")
    out += ["", "## 원인 읽기 — 같이 움직인 숫자(위클리)", "", "| 읽기 | 같이 움직인 숫자 | 원인 자리 | 바꿀 방향 |", "|---|---|---|---|"]
    out += [f"| {p[0]} | {p[1]} | {p[2]} | {p[3]} |" for p in data["patterns"]]
    out += ["", "## 헷갈리기 쉬운 것", ""] + [f"- **{i[0]}** — {i[1]}" for i in data["appendix"]["illusions"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(OUT, len(checks), "항목")
    cat = [{"node": c[0], "r": c[1], "q": c[2], "where": c[3], "bad": c[4], "todo": c[5], "basis": basis[c[6]]["name"]} for c in checks]
    eng = ROOT / "engine" / "checklist.json"
    eng.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(eng)


if __name__ == "__main__":
    main()
