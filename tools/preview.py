"""README.md를 GitHub이 렌더링하는 그대로 그려서 라이트/다크를 나란히 합성한다.

GitHub의 마크다운 API로 HTML을 받고 github-markdown-css를 입히므로,
직접 흉내 낸 레이아웃이 아니라 실제와 같은 결과를 본다.

주의: API의 "gfm" 모드는 댓글용이라 소프트 줄바꿈을 <br>로 바꾼다. github.com의
.md 파일 렌더링은 그렇지 않으므로 "markdown" 모드를 쓴다(라이브 HTML로 확인함).

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


def render_markdown(md: str) -> str:
    req = urllib.request.Request(
        "https://api.github.com/markdown",
        data=json.dumps({"text": md, "mode": "markdown"}).encode("utf-8"),
        headers={"content-type": "application/json",
                 "accept": "application/vnd.github+json",
                 "User-Agent": "pinn99k-readme-preview/1.0"},
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8")


def localize_assets(html_: str) -> str:
    """상대경로 이미지를 로컬 파일 URI로 — 아직 push 안 한 변경도 보이게."""
    def sub(m: re.Match) -> str:
        attr, path = m.group(1), m.group(2)
        return f'{attr}="{(ROOT / path).as_uri()}"'
    return re.sub(r'(src|srcset)="(assets/[^"]+)"', sub, html_)


def unwrap_picture_links(html_: str) -> str:
    """<picture> 안의 <img>를 감싼 <a>를 벗긴다.

    마크다운 API는 이미지를 원본 링크로 감싸지만 github.com의 .md 렌더링은
    그러지 않는다. <img>가 <picture>의 직계 자식이 아니면 HTML 스펙상 <source>가
    무시되어 다크 모드 분기가 죽으므로, 실제와 맞추려면 벗겨야 한다.
    """
    return re.sub(
        r"<a[^>]*>\s*(<img[^>]*>)\s*</a>",
        lambda m: m.group(1),
        html_,
    )


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

# @import는 다른 규칙보다 앞에 와야 한다. 뒤에 붙이면 통째로 무시되고
# 다크 패널이 라이트 CSS로 그려진다 — 한 번 당했으므로 테마별로 맨 앞에 둔다.
EXPECTED_BG = {"light": "rgb(255, 255, 255)", "dark": "rgb(13, 17, 23)"}


def css_for(theme: str) -> str:
    sheet = f"github-markdown-{theme}.css"
    return f'@import url("{CSS_BASE}/{sheet}");\n' + BASE_RULES

DOC = """<!doctype html><meta charset=utf-8>
<style>%(css)s</style><body>%(panel)s</body>"""


def main() -> None:
    out = TOOLS / ("preview.png" if BODY_W == 880 else f"preview-{BODY_W}.png")
    try:
        body = unwrap_picture_links(
            localize_assets(render_markdown(README.read_text(encoding="utf-8")))
        )
    except Exception as e:
        raise SystemExit(f"GitHub 마크다운 API 호출 실패: {e}")

    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            # color_scheme을 걸어야 <picture>의 prefers-color-scheme 분기가 실제로 탄다
            pg = browser.new_page(
                device_scale_factor=2,
                viewport={"width": BODY_W + PANEL_PAD * 2, "height": 900},
                color_scheme=theme,
            )
            tmp = TOOLS / f".preview-{theme}.tmp.html"
            tmp.write_text(DOC % {"css": css_for(theme),
                                  "panel": panel(theme, body)}, encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(900)
            used = pg.eval_on_selector(
                ".markdown-body img", "e => e.currentSrc.split('/').pop()"
            )
            expected = f"header-{theme}.png"
            if used != expected:
                raise SystemExit(
                    f"{theme} 패널이 {used}를 썼습니다 (기대: {expected}) — "
                    "다크 모드 분기가 깨졌습니다"
                )
            # 스타일시트가 실제로 먹었는지 확인한다 (@import 위치를 틀리면 조용히 무시된다)
            bg = pg.eval_on_selector(
                ".markdown-body", "e => getComputedStyle(e).backgroundColor"
            )
            if bg != EXPECTED_BG[theme]:
                raise SystemExit(
                    f"{theme} 패널 본문 배경이 {bg} 입니다 "
                    f"(기대: {EXPECTED_BG[theme]}) — github-markdown-{theme}.css "
                    "가 적용되지 않았습니다"
                )
            shot = TOOLS / f".panel-{theme}.png"
            pg.locator(".panel").screenshot(path=str(shot))
            shots.append(shot)
            pg.close()
            tmp.unlink(missing_ok=True)
        browser.close()

    from PIL import Image
    ims = [Image.open(s) for s in shots]
    canvas = Image.new("RGB", (sum(i.width for i in ims), max(i.height for i in ims)))
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
