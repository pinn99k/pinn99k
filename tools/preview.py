"""README.md를 GitHub이 렌더링하는 그대로 그려서 라이트/다크를 나란히 합성한다.

GitHub의 마크다운 API로 HTML을 받고 github-markdown-css를 입힌 뒤, GitHub과
같은 방식으로 MathJax를 돌린다. 직접 흉내 낸 레이아웃이 아니라 실제와 같다.

주의 1: API의 "gfm" 모드는 댓글용이라 소프트 줄바꿈을 <br>로 바꾼다. github.com의
  .md 파일 렌더링은 그렇지 않다. 다만 수식($...$)은 gfm 모드에서만 인식되므로
  gfm으로 받되, 아래에서 추가된 <br>을 걷어낸다.
주의 2: @import는 다른 규칙보다 앞에 와야 한다. 뒤에 두면 통째로 무시된다.

사용: python tools/preview.py [본문폭]   기본 880(데스크톱), 390이면 모바일
출력: tools/preview.png / tools/preview-{폭}.png
"""

import json
import pathlib
import re
import sys
import urllib.request

from playwright.sync_api import sync_playwright

TOOLS = pathlib.Path(__file__).parent
ROOT = TOOLS.parent
README = ROOT / "README.md"

BODY_W = int(sys.argv[1]) if len(sys.argv) > 1 else 880
PANEL_PAD = 28
CSS_BASE = "https://cdn.jsdelivr.net/npm/github-markdown-css@5.9.0"
MATHJAX = ("https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/"
           "tex-mml-chtml.min.js")

EXPECTED_BG = {"light": "rgb(255, 255, 255)", "dark": "rgb(13, 17, 23)"}


def render_markdown(md: str) -> str:
    req = urllib.request.Request(
        "https://api.github.com/markdown",
        data=json.dumps({"text": md, "mode": "gfm"}).encode("utf-8"),
        headers={"content-type": "application/json",
                 "accept": "application/vnd.github+json",
                 "User-Agent": "pinn99k-readme-preview/1.0"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8")


def unwrap_math(html_: str) -> str:
    """<math-renderer>를 벗겨 안의 $...$만 남긴다 — MathJax가 그걸 조판한다."""
    return re.sub(r"<math-renderer[^>]*>(.*?)</math-renderer>",
                  lambda m: m.group(1), html_, flags=re.S)


def drop_soft_breaks(html_: str) -> str:
    """gfm 모드가 소프트 줄바꿈 자리에 넣은 <br>을 걷어낸다.

    .md 파일 렌더링은 소프트 줄바꿈을 <br>로 바꾸지 않는다(라이브 HTML로 확인).
    README에 직접 쓴 <br>은 줄 끝에 붙어 있고, gfm이 넣은 것은 줄바꿈 바로
    앞에 따로 생기므로 '<br>\\n'이 연달아 두 번 나온 경우의 뒤쪽만 지운다.
    """
    return html_.replace("<br>\n<br>\n", "<br>\n").replace("<br><br>\n", "<br>\n")


def panel(theme: str, body: str) -> str:
    return (f'<div class="panel {theme}">'
            f'<article class="markdown-body">{body}</article>'
            f'</div>')


BASE_RULES = f"""
*{{box-sizing:border-box}}
body{{margin:0;display:flex}}
.panel{{padding:{PANEL_PAD}px;width:{BODY_W + PANEL_PAD * 2}px}}
.panel.light{{background:#ffffff}}
.panel.dark{{background:#0d1117}}
.markdown-body{{width:{BODY_W}px}}
"""


def css_for(theme: str) -> str:
    return (f'@import url("{CSS_BASE}/github-markdown-{theme}.css");\n'
            + BASE_RULES)


DOC = """<!doctype html><meta charset=utf-8>
<script>window.MathJax={tex:{inlineMath:[['$','$']]},options:{enableMenu:false}};</script>
<script src="%(mathjax)s"></script>
<style>%(css)s</style><body>%(panel)s</body>"""


def main() -> None:
    out = TOOLS / ("preview.png" if BODY_W == 880 else f"preview-{BODY_W}.png")
    try:
        body = drop_soft_breaks(
            unwrap_math(render_markdown(README.read_text(encoding="utf-8")))
        )
    except Exception as e:
        raise SystemExit(f"GitHub 마크다운 API 호출 실패: {e}")

    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            pg = browser.new_page(
                device_scale_factor=2,
                viewport={"width": BODY_W + PANEL_PAD * 2, "height": 900},
                color_scheme=theme,
            )
            tmp = TOOLS / f".preview-{theme}.tmp.html"
            tmp.write_text(DOC % {"mathjax": MATHJAX, "css": css_for(theme),
                                  "panel": panel(theme, body)}, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.wait_for_timeout(3500)   # MathJax 조판 대기
            # 스타일시트가 실제로 먹었는지 (@import 위치를 틀리면 조용히 무시된다)
            bg = pg.eval_on_selector(
                ".markdown-body", "e => getComputedStyle(e).backgroundColor")
            if bg != EXPECTED_BG[theme]:
                raise SystemExit(
                    f"{theme} 패널 본문 배경이 {bg} 입니다 "
                    f"(기대: {EXPECTED_BG[theme]}) — "
                    f"github-markdown-{theme}.css 가 적용되지 않았습니다")
            # 수식을 쓴 경우에만, 조판이 끝났는지 검사한다 (원시 TeX 노출 = 실패)
            if "$" in README.read_text(encoding="utf-8"):
                state = pg.evaluate("""() => ({
                    typeset: document.querySelectorAll('mjx-container').length,
                    raw: document.body.innerText.includes('\\\\textsf'),
                })""")
                if state["raw"] or state["typeset"] == 0:
                    raise SystemExit(
                        f"{theme} 패널에서 수식이 조판되지 않았습니다 "
                        f"(mjx-container {state['typeset']}개, 원시 TeX 노출 "
                        f"{state['raw']})")
            shot = TOOLS / f".panel-{theme}.png"
            pg.locator(".panel").screenshot(path=str(shot))
            shots.append(shot)
            pg.close()
            tmp.unlink(missing_ok=True)
        browser.close()

    from PIL import Image
    ims = [Image.open(s) for s in shots]
    canvas = Image.new("RGB", (sum(i.width for i in ims),
                               max(i.height for i in ims)))
    x = 0
    for i in ims:
        canvas.paste(i, (x, 0))
        x += i.width
    canvas.save(out)
    for i in ims:
        i.close()
    for s in shots:
        s.unlink(missing_ok=True)
    print(f"{out.relative_to(ROOT)} 생성 (본문 폭 {BODY_W}px)")


if __name__ == "__main__":
    main()
