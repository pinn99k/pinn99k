"""프로젝트 썸네일을 만든다.

- SIA: cupid_project의 화면 시안에서 뽑은 대시보드 캡처를 둥근 모서리로 다듬는다.
  (원본 캡처는 tools/sources/sia-dashboard.png 에 둔다)
- Java HTTP Server: 실제 클래스 구성을 그대로 쓴 요청 처리 흐름 카드를 렌더한다.
  UI가 없는 프로젝트라 터미널 톤의 다이어그램으로 대신한다. 라이트/다크 공용.

사용: python tools/make_thumbs.py
출력: assets/thumb-sia.png, assets/thumb-java-http-server.png
"""

import pathlib

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

TOOLS = pathlib.Path(__file__).parent
ROOT = TOOLS.parent
OUT = ROOT / "assets"
SRC = TOOLS / "sources"
FONTS = (TOOLS / "fonts").as_uri()

RADIUS = 14 * 2  # 2x 기준


def round_corners(im: Image.Image, radius: int) -> Image.Image:
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, im.width - 1, im.height - 1], radius=radius, fill=255
    )
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def build_sia() -> None:
    src = SRC / "sia-dashboard.png"
    if not src.exists():
        raise SystemExit(f"{src} 가 없습니다 — 화면 캡처를 먼저 넣으세요")
    im = Image.open(src)
    # 하단 조작 버튼 바를 잘라 비율을 눕힌다
    crop_h = int(im.height * 0.88)
    im = im.crop((0, 0, im.width, crop_h))
    im = im.resize((1600, int(1600 * im.height / im.width)), Image.LANCZOS)
    round_corners(im, RADIUS).save(OUT / "thumb-sia.png")
    print(f"  assets/thumb-sia.png  {im.size[0]}x{im.size[1]}")


JAVA_CSS = f"""
@font-face{{font-family:P;src:url({FONTS}/Pretendard-Medium.woff2);font-weight:500}}
@font-face{{font-family:P;src:url({FONTS}/Pretendard-Bold.woff2);font-weight:700}}
@font-face{{font-family:M;src:url({FONTS}/ibm-plex-mono-latin-400-normal.woff2);font-weight:400}}
@font-face{{font-family:M;src:url({FONTS}/ibm-plex-mono-latin-500-normal.woff2);font-weight:500}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:transparent}}
body{{font-family:P,sans-serif;-webkit-font-smoothing:antialiased}}
.card{{width:800px;height:396px;background:#14181f;border-radius:14px;
      padding:34px 38px;color:#e6edf3;position:relative;overflow:hidden}}
.bar{{display:flex;gap:7px;margin-bottom:28px}}
.bar i{{width:11px;height:11px;border-radius:50%;background:#30363d;display:block}}
.bar i:first-child{{background:#ff7a45}}
.flow{{display:flex;align-items:stretch}}
.step{{flex:1;padding:18px 14px 17px;border:1.5px solid #30363d;border-radius:10px;
      background:#1b212b}}
.step .k{{font-family:M,monospace;font-size:15px;font-weight:500;color:#ff7a45;
        letter-spacing:0}}
.step .v{{font-size:15px;color:#9aa6b2;margin-top:8px;line-height:1.35}}
.arrow{{display:flex;align-items:center;color:#5a6472;font-size:19px;padding:0 9px;
       font-family:M,monospace}}
.route{{margin-top:26px;padding:17px 20px;background:#1b212b;border-radius:10px;
       font-family:M,monospace;font-size:16px;color:#9aa6b2;letter-spacing:0}}
.route b{{color:#e6edf3;font-weight:500}}
.route s{{color:#5a6472;text-decoration:none;padding:0 12px}}
/* 한글은 Pretendard로 — mono에 한글을 태우면 자간이 벌어진다 */
.note{{margin-top:22px;font-size:16px;color:#9aa6b2;line-height:1.85}}
.note code{{font-family:M,monospace;font-size:15px;color:#e6edf3;letter-spacing:0}}
.tag{{position:absolute;right:38px;bottom:30px;font-family:M,monospace;
     font-size:14px;color:#5a6472}}
"""

JAVA_HTML = """
<div class="card" id="el">
  <div class="bar"><i></i><i></i><i></i></div>
  <div class="flow">
    <div class="step"><div class="k">ServerSocket</div>
      <div class="v">accept 루프</div></div>
    <div class="arrow">&rsaquo;</div>
    <div class="step"><div class="k">HttpRequest</div>
      <div class="v">요청 파싱</div></div>
    <div class="arrow">&rsaquo;</div>
    <div class="step"><div class="k">ServletManager</div>
      <div class="v">path 분기</div></div>
    <div class="arrow">&rsaquo;</div>
    <div class="step"><div class="k">Command</div>
      <div class="v">action 분기</div></div>
  </div>
  <div class="route">
    <b>/user?action=borrow</b><s>&rarr;</s>UserController<s>&rarr;</s>BorrowCommand
  </div>
  <div class="note">
    <code>SessionManager</code> UUID 세션 직접 관리<br>
    <code>Repository · Facade · Command</code> 도서관 도메인에 적용
  </div>
  <div class="tag">no framework</div>
</div>
"""


def build_java() -> None:
    tmp = TOOLS / ".thumb.tmp.html"
    tmp.write_text(
        f"<!doctype html><meta charset=utf-8><style>{JAVA_CSS}</style>"
        f"<body>{JAVA_HTML}</body>",
        encoding="utf-8",
    )
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(device_scale_factor=2,
                        viewport={"width": 1000, "height": 600})
        pg.goto(tmp.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(250)
        path = OUT / "thumb-java-http-server.png"
        pg.locator("#el").screenshot(path=str(path), omit_background=True)
        b.close()
    tmp.unlink(missing_ok=True)
    print(f"  assets/thumb-java-http-server.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_sia()
    build_java()
    print("done")
