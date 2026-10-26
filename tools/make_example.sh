#!/bin/zsh
# 예시 대시보드(v4.1) 다시 만들기 — 지어낸 'A사(예시)' 데이터로 여러 날짜 실행 폴더를 만들고 판정 · 렌더한다.
#   zsh tools/make_example.sh [작업 폴더(기본: ./runs_example)]
# 결과: dashboard/ROAS_점검_대시보드_v4.1_데일리.html · _위클리.html 을 덮어쓴다.
# 10/22 이전 날짜는 행사 페이지가 아직 열려 있던 것으로(web.json의 '종료' 문구 제거) 입력 예시만 고친다.
set -e
ROOT=${0:A:h:h}
WORK=${1:-$ROOT/runs_example}
run() {  # run 출력폴더 앞기간일수 daily|weekly 날짜...
  local OUT=$1 DAYS=$2 MODE=$3; shift 3
  rm -rf "$OUT"; python3 "$ROOT/engine/make_sample.py" --out "$OUT" --days $DAYS >/dev/null
  local ADV="$OUT/A사(예시)" SRC="$OUT/A사(예시)/2026-10-22-daily" R
  for d in "$@"; do
    if [ "$d" != "2026-10-22" ]; then
      R="$ADV/$d-$MODE"; mkdir -p "$R"; cp "$SRC"/*.json "$R/"
      python3 -c "import json,sys;p=sys.argv[1];w=json.load(open(p));[x.update(ended_words=[]) for x in w['pages']];json.dump(w,open(p,'w'),ensure_ascii=False)" "$R/web.json"
    else R="$SRC"; fi
    if [ "$MODE" = weekly ]; then python3 "$ROOT/engine/analyze.py" --run "$R" --date $d --advertiser "A사(예시)" --weekly >/dev/null
    else python3 "$ROOT/engine/analyze.py" --run "$R" --date $d --advertiser "A사(예시)" >/dev/null; fi
  done
  echo "$R"
}
D=$(run "$WORK/daily" 28 daily 2026-10-09 2026-10-10 2026-10-13 2026-10-14 2026-10-15 2026-10-16 2026-10-17 2026-10-19 2026-10-20 2026-10-21 2026-10-22)
W=$(run "$WORK/weekly" 63 weekly 2026-09-24 2026-10-01 2026-10-08 2026-10-15 2026-10-22)
python3 "$ROOT/engine/render_board.py" --run "$D" --out "$ROOT/dashboard/ROAS_점검_대시보드_v4.1_데일리.html"
python3 "$ROOT/engine/render_board.py" --run "$W" --out "$ROOT/dashboard/ROAS_점검_대시보드_v4.1_위클리.html"
