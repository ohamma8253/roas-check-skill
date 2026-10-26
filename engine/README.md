# 점검 엔진 — 자동 수집 · 분석 · 점검 회로 대시보드

스킬(`skill/roas-check`)은 웹 단계 안내만 맡고, 자동으로 데이터를 모아 판정하고 대시보드를 그리는 일은 이 엔진이 맡는다. 아래 경로의 `scripts/`는 이 폴더(`engine/`)를 뜻한다.

대시보드: v2 평면 점검 회로(`board_template.html`) — 신호판 → 관문 → 자리 카드, 점검반(체크리스트 `checklist.json` 램프). 예전 3D 화면은 `render_board.py --v1`.

스크립트는 파이썬 3 표준 라이브러리만 쓴다. 대화만 되는 환경에서는 이 문서의 '판정'만 참고하고 계산은 직접 한다.

## 실행 폴더
```
runs/<광고주>/
  snapshots/<날짜>.json        # 설정 스냅샷 — 다음 실행의 '어제와 같나' 기준
  <날짜>-daily/ 또는 <날짜>-weekly/
    insights.json   meta.json   activities.json   pixel.json   insights_weekly.json
    web.json        site.json   peers.json
    result.json     report.md   board.html   feedback.jsonl
```
없는 파일은 그 자리를 `못 봄`으로 남긴다.

## 흐름
```
# 1) 성과 — 둘 중 하나
python3 scripts/collect_meta.py --account act_123 --date 2026-10-22 --out RUN [--weekly] [--pixel 456]   # META_ACCESS_TOKEN 환경변수 필요
python3 scripts/import_export.py --run RUN --level campaign 캠페인_일별.csv [--level ad 광고_일별.csv]     # 광고 관리자 내보내기

# 2) 웹 상태
python3 scripts/web_check.py --run RUN [--home https://shop.example.com] [--url 주소 ...] [--inapp]

# 3) 점검 → 보고서 · 대시보드
python3 scripts/analyze.py --run RUN --date 2026-10-22 [--weekly] --advertiser A사
python3 scripts/render_board.py --run RUN        # 화면 틀: scripts/board_template.html(3D 점검 회로)
```
메타 API는 읽기만 한다(광고를 켜고 끄지 않는다). 토큰은 환경변수로만 넘기고 출력하지 않는다.

## 파일 형식
| 파일 | 내용 | 만드는 법 |
|---|---|---|
| `insights.json` | `[{level: account·campaign·adset·ad, id, name, date, campaign_id, adset_id, spend, impressions, reach, frequency, clicks(링크 클릭), lpv, view_content, add_to_cart, initiate_checkout, purchases, revenue}]` | collect_meta · import_export |
| `meta.json` | `{account:{account_status, spend_cap, amount_spent, currency}, campaigns:[{id,name,effective_status,objective,daily_budget,...}], adsets:[{..., bid_strategy, optimization_goal, promoted_object, attribution_spec, excluded_audiences, learning_status}], ads:[{id,name,effective_status,issues,link_url}]}` | collect_meta |
| `activities.json` | `[{event_type, event_time, actor_name, object_id, object_name}]` | collect_meta |
| `pixel.json` | `[{hour, event, count, source: WEB_ONLY·SERVER_ONLY}]` | collect_meta --pixel |
| `web.json` | `{home:{...}, pages:[{url, status, final_url, chain, ms, kept_utm, kept_fbclid, went_home, soldout_words, ended_words, has_pixel, has_gtm}]}` | web_check |
| `site.json` | `{daily:[{date, orders, revenue}], promos:[{name, match(캠페인 이름에 들어간 말), start, end, url}], special_days:[{date, name}]}` | 광고주에게 받아 직접 쓴다 |
| `peers.json` | `[{name, date, roas}]` 같은 업종 광고주 | 직접 운영하는 계정에서 |

## 연결하면 켜지는 자리
| 데이터 | 켜지는 자리 |
|---|---|
| 메타 성과(하루 단위) | 신호판, 자사 › 도착 · 장바구니 · 결제, 매체 › 광고 |
| 메타 설정 스냅샷 · 앞선 스냅샷 · 변경 이력 | 매체 › 계정 · 캠페인 · 광고세트 · 광고 |
| 주 단위 성과(빈도 · 도달) | 매체 › 광고세트(타겟 폭) · 광고(닳음) |
| 픽셀 이벤트 수 | 자사 › 측정 태그 |
| 웹 점검기 | 자사 › 도착 · 랜딩 · 상품 · 측정 태그 |
| 자사몰 매출 · 행사 달력 | 신호판, 자사 › 구매 완료, 매체 › 캠페인(행사 켜짐 · 꺼짐), 시장 › 달력 |
| 같은 업종 묶음 | 시장 › 업종 흐름 |
| 검색 수요 | 시장 › 수요 |
| GA4 | 자사 › 랜딩 · 결제(랜딩별 · 단계별) |

## 판정 손잡이(`scripts/lib.py`)
표준값이 아니라 판정 방식의 손잡이다. 피드백이 쌓이면 고친다.
`BASE_DAYS=14` 비교 기간 · `MIN_BASE_DAYS=7` 평소 범위 최소 일수 · `MIN_EVENTS=20` 비율 판정 최소 분모 ·
`CROWD_SHARE=0.5` 몰림 · `SPREAD_SHARE=0.7` · `SPREAD_RATE=0.5` 퍼짐 · `STREAK_TOL=0.02` 몇 주째에서 무시할 흔들림

## 웹 점검기가 못 보는 것
화면 깨짐 · 이벤트 실제 발동 · 결제 앱 전환 · 로그인 뒤 화면. 이건 사용자에게 휴대폰으로 열어 봐 달라고 하거나, 브라우저 도구가 있으면 그걸로 본다.
