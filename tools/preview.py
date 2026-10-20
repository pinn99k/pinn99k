"""assets/*.png를 GitHub README 본문 폭(880px)에 얹어 라이트/다크를 나란히 합성한다.

실제 README 레이아웃(DESIGN.md 6절)을 그대로 재현하므로 육안 검수용으로 쓴다.
사용: python tools/preview.py
출력: tools/preview.png
"""

import html
import json
import pathlib

from playwright.sync_api import sync_playwright

TOOLS = pathlib.Path(__file__).parent
ROOT = TOOLS.parent
ASSETS = ROOT / "assets"
OUT = TOOLS / "preview.png"

D = json.loads((TOOLS / "design.json").read_text(encoding="utf-8"))

BODY_W = 880          # GitHub README 본문 폭
PANEL_PAD = 28
GH_SANS = ("-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',"
           "Helvetica,Arial,sans-serif")


def img(name: str, theme: str, alt: str, width: str) -> str:
    src = (ASSETS / f"{name}-{theme}.png").as_uri()
    return f'<img src="{src}" alt="{html.escape(alt)}" width="{width}">'


def panel(theme: str) -> str:
    e = html.escape
    rm = D["readme"]
    cards = "".join(
        f'<span class="c">{img("card-" + c["slug"], theme, c["alt"], "32%")}</span>'
        for c in D["cards"]
    )
    intro = "<br>".join(e(line) for line in rm["intro"])
    return f"""
<div class="panel {theme}">
  <div class="body">
    {img("header", theme, D["header"]["alt"], "100%")}
    <p>{intro}</p>
    <p class="cards">{cards}</p>
    <p><b>Now</b> — {e(rm['now']['text'])} &rarr;
       <a href="#">{e(rm['now']['label'])}</a></p>
    <p><b>Contact</b> — <a href="#">{e(rm['contact']['email'])}</a> ·
       <a href="#">{e(rm['contact']['blog'])}</a></p>
  </div>
</div>"""


CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{display:flex;gap:0;font-family:{GH_SANS};font-size:16px;line-height:1.5}}
.panel{{padding:{PANEL_PAD}px;width:{BODY_W + PANEL_PAD * 2}px}}
.panel.light{{background:#ffffff;color:#1f2328}}
.panel.dark{{background:#0d1117;color:#f0f3f6}}
.panel.light a{{color:#0969da}} .panel.dark a{{color:#4493f8}}
.body>*+*{{margin-top:16px}}
.cards{{text-align:center;font-size:0}}
.c+.c{{margin-left:1.6%}}
img{{vertical-align:middle}}
"""


def main() -> None:
    missing = [
        f"{n}-{t}.png"
        for t in D["themes"]
        for n in ["header"] + [f"card-{c['slug']}" for c in D["cards"]]
        if not (ASSETS / f"{n}-{t}.png").exists()
    ]
    if missing:
        raise SystemExit(f"assets 누락: {', '.join(missing)} — 먼저 render.py 실행")

    doc = ("<!doctype html><meta charset=utf-8>"
           f"<style>{CSS}</style><body>{panel('light')}{panel('dark')}</body>")
    tmp = TOOLS / ".preview.tmp.html"
    tmp.write_text(doc, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(
            device_scale_factor=2,
            viewport={"width": (BODY_W + PANEL_PAD * 2) * 2, "height": 900},
        )
        pg.goto(tmp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT), full_page=True)
        browser.close()
    tmp.unlink(missing_ok=True)
    print(f"{OUT.relative_to(ROOT)} 생성")


if __name__ == "__main__":
    main()
