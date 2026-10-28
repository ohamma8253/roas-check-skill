#!/usr/bin/env python3
"""결과 블록 JSON으로 '대시보드에서 보기' 링크를 만든다(표준 라이브러리만, 파이썬 3.8+).

  python3 make_link.py 결과.json            링크 한 줄을 찍는다
  python3 make_link.py < 결과.json          표준 입력으로 받아도 된다
  python3 make_link.py 결과.json --open     링크를 기본 브라우저로도 연다
  python3 make_link.py 결과.json --check <링크>   링크를 되풀어 같은 JSON인지 본다
  python3 make_link.py --check <링크>       되푼 JSON을 찍는다

입력에 ```roas-check 울타리나 앞뒤 글이 섞여 있으면 JSON 부분만 골라낸다(여럿이면 마지막 것).
링크 형식: <주소>#r=1.<crc32 8자리>.<base64url(zlib(JSON UTF-8))> — crc32는 압축 전 바이트의 것.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import webbrowser
import zlib

BASE = "https://ohamma8253.github.io/roas-check-skill/"
VERSION = "1"
FORMAT = "roas-check/1"


def fail(msg):
    sys.stderr.write("오류: " + msg + "\n")
    sys.exit(1)


def pick_block(text):
    """글에서 결과 블록 JSON을 찾아 원래 글 그대로 돌려준다."""
    dec = json.JSONDecoder()
    found, first_err, i = [], None, 0
    while True:
        i = text.find("{", i)
        if i < 0:
            break
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError as e:
            if first_err is None:
                first_err = e
            i += 1
            continue
        if isinstance(obj, dict) and "형식" in obj:
            found.append((obj, text[i:end]))
        i = end
    if not found:
        why = " (JSON 문법 오류: %s)" % first_err if first_err else ""
        fail("결과 블록 JSON을 찾지 못했습니다" + why)
    obj, raw = found[-1]
    if obj.get("형식") != FORMAT:
        fail("형식이 %r입니다(%r이어야 합니다)" % (obj.get("형식"), FORMAT))
    return raw


def make_value(raw):
    data = raw.encode("utf-8")
    body = base64.urlsafe_b64encode(zlib.compress(data, 9)).decode("ascii").rstrip("=")
    return "%s.%08x.%s" % (VERSION, zlib.crc32(data) & 0xFFFFFFFF, body)


def read_link(link):
    """링크(또는 #r= 뒤 값)를 되풀어 JSON 바이트를 돌려준다."""
    value = link.strip()
    for mark in ("#r=", "r="):
        if mark in value:
            value = value.split(mark, 1)[1]
            break
    parts = value.split(".", 2)
    if len(parts) != 3 or parts[0] != VERSION or len(parts[1]) != 8:
        fail("링크 값의 모양이 '1.<crc32 8자리>.<몸통>'이 아닙니다")
    try:
        crc = int(parts[1], 16)
        data = zlib.decompress(base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4)))
    except ValueError as e:
        fail("링크가 잘렸거나 바뀌었습니다(%s)" % e)
    except zlib.error as e:
        fail("링크가 잘렸거나 바뀌었습니다(%s)" % e)
    if zlib.crc32(data) & 0xFFFFFFFF != crc:
        fail("crc32가 맞지 않습니다(링크가 잘렸거나 바뀌었습니다)")
    return data


def open_in_browser(url):
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", url], check=True)
        elif os.name == "nt":
            os.startfile(url)
        elif shutil.which("xdg-open"):
            subprocess.run(["xdg-open", url], check=True)
        elif not webbrowser.open(url):
            raise OSError("열 브라우저가 없습니다")
    except (OSError, subprocess.CalledProcessError) as e:
        sys.stderr.write("브라우저를 열지 못했습니다(%s). 위 링크를 복사해 여세요.\n" % e)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="결과 블록 JSON으로 대시보드 링크를 만든다.")
    ap.add_argument("file", nargs="?", help="결과 블록 JSON 파일('-'면 표준 입력, 없으면 --check 아닐 때 표준 입력)")
    ap.add_argument("--open", action="store_true", help="만든 링크를 기본 브라우저로 연다")
    ap.add_argument("--check", metavar="링크", help="링크를 되풀어 입력 JSON과 같은지 본다")
    args = ap.parse_args()

    if args.file and args.file != "-":
        with open(args.file, "rb") as f:
            text = f.read().decode("utf-8-sig")
    elif args.check and not args.file:
        text = ""  # --check만 주면 표준 입력을 기다리지 않는다(견주려면 파일이나 '-')
    else:
        text = sys.stdin.buffer.read().decode("utf-8-sig")

    if args.check:
        data = read_link(args.check)
        try:
            obj = json.loads(data.decode("utf-8"))
        except ValueError as e:
            fail("되푼 내용이 JSON이 아닙니다(%s)" % e)
        if not text.strip():
            sys.stdout.write(data.decode("utf-8") + "\n")
            return
        raw = pick_block(text).encode("utf-8")
        if raw != data:
            fail("다릅니다: 입력 %d바이트 · 링크 %d바이트" % (len(raw), len(data)))
        print("같음: %d바이트 · crc32 %08x · %s · %s · %s" % (
            len(data), zlib.crc32(data) & 0xFFFFFFFF,
            obj.get("광고주", "?"), obj.get("날짜", "?"), obj.get("리듬", "?")))
        return

    if not text.strip():
        fail("입력이 비었습니다(결과 블록 JSON 파일 경로를 주거나 표준 입력으로 넘기세요)")
    url = BASE + "#r=" + make_value(pick_block(text))
    print(url)
    if args.open and open_in_browser(url):
        sys.stderr.write("대시보드를 브라우저로 열었습니다.\n")


if __name__ == "__main__":
    main()
