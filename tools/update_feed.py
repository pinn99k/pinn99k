"""velog RSS에서 최근 글을 읽어 README.md의 마커 사이를 갈아끼운다.

표준 라이브러리만 쓴다 (GitHub Actions에서 의존성 설치 없이 돌리기 위해).
사용: python tools/update_feed.py
종료코드: 0 = 성공(변경 여부 무관), 1 = 실패
"""

import datetime as dt
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://api.velog.io/rss/@pinn99u"
COUNT = 5
START = "<!-- posts:start -->"
END = "<!-- posts:end -->"
README = pathlib.Path(__file__).parent.parent / "README.md"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pinn99k-readme/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def parse_date(raw: str) -> str:
    """RFC822 → YYYY.MM.DD. 못 읽으면 빈 문자열."""
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt).strftime("%Y.%m.%d")
        except ValueError:
            continue
    return ""


def items(xml: bytes) -> list[str]:
    root = ET.fromstring(xml)
    out = []
    for item in list(root.iterfind(".//item"))[:COUNT]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = parse_date(item.findtext("pubDate") or "")
        if not title or not link:
            continue
        # 링크 텍스트 안의 대괄호는 이스케이프해야 링크가 깨지지 않는다
        title = title.replace("[", r"\[").replace("]", r"\]")
        out.append(f"- [{title}]({link})" + (f" · {date}" if date else ""))
    return out


def main() -> int:
    try:
        lines = items(fetch(FEED))
    except Exception as e:  # 피드가 죽어도 README를 비우지 않는다
        print(f"피드를 못 읽었습니다 ({e}) — README 그대로 둡니다", file=sys.stderr)
        return 1
    if not lines:
        print("피드에 글이 없습니다 — README 그대로 둡니다", file=sys.stderr)
        return 1

    text = README.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END), re.S
    )
    if not pattern.search(text):
        print(f"README에 {START} / {END} 마커가 없습니다", file=sys.stderr)
        return 1

    block = START + "\n" + "\n".join(lines) + "\n" + END
    new = pattern.sub(lambda _: block, text, count=1)
    if new == text:
        print("변경 없음")
        return 0
    README.write_text(new, encoding="utf-8")
    print(f"글 {len(lines)}개 갱신")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
