"""DESIGN.md 기준 헤더·카드 PNG 렌더러.

내용·토큰은 전부 design.json에서 읽는다. 이 파일에는 문구를 두지 않는다.
사용: python tools/render.py
출력: assets/header-{light,dark}.png, assets/card-{slug}-{light,dark}.png
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
R, TYPE, HD, CD = D["render"], D["type"], D["header"], D["card"]


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


def t(key: str, extra: str = "") -> str:
    """type 토큰 하나를 인라인 CSS 선언 문자열로."""
    s = TYPE[key]
    css = f"font-size:{s['size']}px;font-weight:{s['weight']};color:var(--{s['color']})"
    css += ";font-family:M,P,monospace;letter-spacing:0" if s.get("mono") else ""
    css += f";letter-spacing:{s['ls']}" if s.get("ls") else ""
    return css + (";" + extra if extra else "")


BASE_CSS = (
    font_faces()
    + """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent}
body{font-family:P,sans-serif;-webkit-font-smoothing:antialiased;letter-spacing:-0.01em}
.frame{background:var(--bg);border:%(bw)spx solid var(--line);border-radius:%(r)spx;
       color:var(--ink);overflow:hidden}
""" % {"bw": R["border"], "r": R["radius"]}
)

HEADER_CSS = """
.header{width:%(w)spx;height:%(h)spx;position:relative;padding:%(py)spx %(px)spx}
.tag{%(tag)s;display:flex;align-items:center;gap:12px}
.dot{width:10px;height:10px;background:var(--accent);display:inline-block;flex:none}
.name{%(name)s;line-height:1;margin-top:30px}
.right{position:absolute;left:%(split)spx;top:46px;
       border-left:%(bw)spx solid var(--line);padding-left:52px}
.line{%(line)s;line-height:1.38}
.line b{color:var(--accent);font-weight:700}
.stack{%(stack)s;position:absolute;left:%(px)spx;right:%(px)spx;bottom:30px}
""" % {
    "w": HD["size"]["w"], "h": HD["size"]["h"],
    "px": HD["pad"]["x"], "py": HD["pad"]["y"],
    "split": HD["split_x"], "bw": R["border"],
    "tag": t("header.tag"), "name": t("header.name"),
    "line": t("header.line"), "stack": t("header.stack"),
}

CARD_CSS = """
.card{width:%(w)spx;height:%(h)spx;padding:%(p)spx %(p)spx 0;display:flex;flex-direction:column}
.top{height:%(top)spx}
.meta{%(meta)s;display:flex;gap:10px;align-items:baseline;white-space:nowrap}
.meta .i{%(index)s}
.title{%(title)s;margin-top:18px;line-height:1.1}
.desc{%(desc)s;margin-top:8px;line-height:1.4}
.hero{border-top:%(bw)spx solid var(--line);padding-top:22px}
.heroval{height:%(hv)spx;display:flex;align-items:flex-end}
.num{%(num)s;line-height:1;white-space:nowrap}
.num.txt{%(txt)s}
.cap{%(cap)s;margin-top:8px}
ul{list-style:none;margin-top:24px}
li{%(point)s;line-height:1.45;padding-left:18px;position:relative;margin-top:9px}
li:first-child{margin-top:0}
li:before{content:"";position:absolute;left:0;top:10px;width:7px;height:2px;background:var(--ink)}
.tags{%(tags)s;margin-top:auto;border-top:%(bw)spx solid var(--line);
      margin-left:-%(p)spx;margin-right:-%(p)spx;padding:18px %(p)spx 20px}
""" % {
    "w": CD["size"]["w"], "h": CD["size"]["h"], "p": CD["pad"],
    "top": CD["slot"]["top"], "hv": CD["slot"]["heroValue"], "bw": R["border"],
    "meta": t("card.meta"), "index": t("card.index"), "title": t("card.title"),
    "desc": t("card.desc"), "num": t("card.heroNum"), "txt": t("card.heroTxt"),
    "cap": t("card.caption"), "point": t("card.point"), "tags": t("card.tags"),
}


def header_html() -> str:
    e = html.escape
    lines = "".join(
        f'<p class="line"><b>{e(l["key"])}</b>{e(l["rest"])}</p>' for l in HD["lines"]
    )
    return f"""
<div class="frame header" id="el">
  <div class="left">
    <div class="tag"><span class="dot"></span>{e(HD['tag'])}</div>
    <div class="name">{e(HD['name'])}</div>
  </div>
  <div class="right">{lines}</div>
  <div class="stack">{e(HD['stack'])}</div>
</div>"""


def card_html(c: dict) -> str:
    e = html.escape
    numcls = "num" if any(ch.isdigit() for ch in c["hero"]) else "num txt"
    points = "".join(f"<li>{e(p)}</li>" for p in c["points"])
    return f"""
<div class="frame card" id="el">
  <div class="top">
    <div class="meta"><span class="i">{e(c['index'])}</span><span>{e(c['meta'])}</span></div>
    <div class="title">{e(c['title'])}</div>
    <div class="desc">{e(c['desc'])}</div>
  </div>
  <div class="hero">
    <div class="heroval"><div class="{numcls}">{e(c['hero'])}</div></div>
    <div class="cap">{e(c['caption'])}</div>
  </div>
  <ul>{points}</ul>
  <div class="tags">{e(c['tags'])}</div>
</div>"""


def page(body: str, css: str, theme: dict) -> str:
    tokens = ":root{" + ";".join(f"--{k}:{v}" for k, v in theme.items()) + "}"
    return (
        "<!doctype html><meta charset=utf-8>"
        f"<style>{BASE_CSS}{tokens}{css}</style><body>{body}</body>"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = TOOLS / ".render.tmp.html"
    jobs = [("header", header_html(), HEADER_CSS)] + [
        (f"card-{c['slug']}", card_html(c), CARD_CSS) for c in D["cards"]
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(
            device_scale_factor=R["device_scale_factor"], viewport=R["viewport"]
        )
        for theme_name, theme in D["themes"].items():
            for name, body, css in jobs:
                tmp.write_text(page(body, css, theme), encoding="utf-8")
                pg.goto(tmp.as_uri())
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(200)
                path = OUT / f"{name}-{theme_name}.png"
                pg.locator("#el").screenshot(path=str(path), omit_background=True)
                print(f"  {path.relative_to(ROOT)}")
        browser.close()
    tmp.unlink(missing_ok=True)
    print("done")


if __name__ == "__main__":
    main()
