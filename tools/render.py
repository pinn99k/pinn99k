"""헤더 이미지 렌더러 (라이트/다크 2장).

README 본문은 마크다운이라 렌더링 대상이 아니다. 프로젝트 썸네일은
make_thumbs.py가 따로 만든다. 토큰·문구는 design.json에서 읽는다.

사용: python tools/render.py
출력: assets/header-{light,dark}.png
"""

import html
import json
import pathlib

from playwright.sync_api import sync_playwright

TOOLS = pathlib.Path(__file__).parent
ROOT = TOOLS.parent
OUT = ROOT / "assets"
FONTS = (TOOLS / "fonts").as_uri()

D = json.loads((TOOLS / "design.json").read_text(encoding="utf-8"))
R, TYPE, HD = D["render"], D["type"], D["header"]


def font_faces() -> str:
    css = ""
    for spec in D["fonts"].values():
        for f in spec["faces"]:
            css += (
                f"@font-face{{font-family:{spec['family']};"
                f"src:url({FONTS}/{f['file']}) format('woff2');"
                f"font-weight:{f['weight']};font-display:block}}"
            )
    return css


def t(key: str) -> str:
    """type 토큰 하나를 인라인 CSS 선언 문자열로."""
    s = TYPE[key]
    css = f"font-size:{s['size']}px;font-weight:{s['weight']};color:var(--{s['color']})"
    if s.get("mono"):
        css += ";font-family:M,P,monospace;letter-spacing:0"
    if s.get("ls"):
        css += f";letter-spacing:{s['ls']}"
    return css


CSS = font_faces() + """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent}
body{font-family:P,sans-serif;-webkit-font-smoothing:antialiased;letter-spacing:-0.01em}
.header{width:%(w)spx;height:%(h)spx;padding:%(p)spx;%(frame)s
        display:flex;flex-direction:column;align-items:center;
        justify-content:center;text-align:center}
.name{%(name)s;line-height:1}
.line{%(line)s;line-height:1.4;margin-top:12px;white-space:nowrap}
.line b{color:var(--accent);font-weight:700}
""" % {
    "w": HD["size"]["w"], "h": HD["size"]["h"], "p": HD["pad"],
    # framed=false면 테두리·배경 없이 글자만 — 페이지 배경 위에 그대로 얹힌다
    "frame": (f"background:var(--bg);border:{R['border']}px solid var(--line);"
              f"border-radius:{R['radius']}px;overflow:hidden;"
              if HD.get("framed", True) else ""),
    "name": t("header.name"), "line": t("header.line"),
}


def header_html() -> str:
    e = html.escape
    line = "".join(f'<b>{e(l["key"])}</b>{e(l["rest"])}' for l in HD["lines"])
    return f"""
<div class="header" id="el">
  <div class="name">{e(HD['name'])}</div>
  <div class="line">{line}</div>
</div>"""


def page(theme: dict) -> str:
    tokens = ":root{" + ";".join(f"--{k}:{v}" for k, v in theme.items()) + "}"
    return ("<!doctype html><meta charset=utf-8>"
            f"<style>{CSS}{tokens}</style><body>{header_html()}</body>")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = TOOLS / ".render.tmp.html"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(
            device_scale_factor=R["device_scale_factor"], viewport=R["viewport"]
        )
        for theme_name, theme in D["themes"].items():
            tmp.write_text(page(theme), encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(200)
            el = pg.locator("#el")
            # 한 줄 소개가 넘치면 헤더 폭을 넘겨 잘린다 — 렌더 시점에 바로 잡는다.
            overflow = el.evaluate(
                "e => {const l = e.querySelector('.line');"
                " return l.scrollWidth - l.clientWidth}"
            )
            if overflow > 0:
                raise SystemExit(
                    f"소개 한 줄이 {overflow}px 넘칩니다 — design.json의 "
                    f"type['header.line'].size를 줄이거나 header.size.w를 키우세요"
                )
            path = OUT / f"header-{theme_name}.png"
            el.screenshot(path=str(path), omit_background=True)
            print(f"  {path.relative_to(ROOT)}")
        browser.close()
    tmp.unlink(missing_ok=True)
    print("done")


if __name__ == "__main__":
    main()
