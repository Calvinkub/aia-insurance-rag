"""Drive the real AIA Q&A web UI in a browser and record it (Playwright, Chromium).

The page is the real FastAPI app at BASE (start it first: uvicorn aia_rag.server:app --port 8000).
A visible cursor and click ripple are injected so the viewer can follow the mouse.
Writes public/demo_raw.webm and public/demo_timeline.json (start/end seconds of each step in the video).
Usage: python tools/record_demo.py
"""
import json
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:8000/"
W, H = 1280, 720

STEPS = [
    ("demo1", "ask", "ระยะเวลารอคอยของ AIA CI Care คือกี่วัน"),
    ("demo2", "ask", "รางวัล Vitality มีกี่ระดับ"),
    ("demo3", "agent", "เปรียบเทียบอายุรับประกันของ AIA CI Care กับ AIA Smart Select"),
    ("demo4", "ask", "AIA CI Care คุ้มครองโรคร้ายแรงระยะรุนแรงกี่โรค"),
]

CURSOR_JS = """
(() => {
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;z-index:99999;width:26px;height:26px;margin:-4px 0 0 -4px;pointer-events:none;' +
    'background:url("data:image/svg+xml;utf8,<svg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27><path d=%27M3 2l7 18 2.6-7.4L20 10z%27 fill=%27black%27 stroke=%27white%27 stroke-width=%271.6%27/></svg>") no-repeat;background-size:contain;left:-50px;top:-50px';
  const add = () => document.body && document.body.appendChild(c);
  document.addEventListener('DOMContentLoaded', add);
  document.addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  document.addEventListener('mousedown', e => {
    const r = document.createElement('div');
    r.style.cssText = `position:fixed;z-index:99998;left:${e.clientX - 20}px;top:${e.clientY - 20}px;width:40px;height:40px;border-radius:50%;` +
      'border:3px solid #c8102e;pointer-events:none;transition:transform .5s,opacity .5s;opacity:.9';
    document.body.appendChild(r);
    requestAnimationFrame(() => { r.style.transform = 'scale(2.2)'; r.style.opacity = '0'; });
    setTimeout(() => r.remove(), 600);
  }, true);
})();
"""


def move_click(page: Page, selector: str) -> None:
    box = page.locator(selector).bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=35)
    page.wait_for_timeout(250)
    page.mouse.down(); page.wait_for_timeout(90); page.mouse.up()


def wait_done(page: Page, timeout_ms: int = 120_000) -> str:
    # The UI sets data-state="done" on #out when the final event has been rendered.
    page.wait_for_selector("#out[data-state=done]", timeout=timeout_ms)
    page.wait_for_timeout(1500)
    return page.inner_text("#out")


def main() -> None:
    timeline = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(ROOT / "public" / "_rec"),
                                  record_video_size={"width": W, "height": H})
        ctx.add_init_script(CURSOR_JS)
        page = ctx.new_page()
        t0 = time.time()
        page.goto(BASE)
        page.wait_for_timeout(1200)
        for name, mode, question in STEPS:
            timeline[name] = {"start": round(time.time() - t0, 2)}
            if mode != page.input_value("#mode"):
                move_click(page, f"[data-mode={mode}]")
                page.wait_for_timeout(500)
            move_click(page, "#q")
            page.fill("#q", "")
            page.type("#q", question, delay=55)
            page.wait_for_timeout(500)
            move_click(page, "#go")
            text = wait_done(page)
            page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
            page.wait_for_timeout(2200)
            timeline[name]["end"] = round(time.time() - t0, 2)
            print(f"== {name} [{mode}] {question}\n{text}\n", flush=True)
            page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            page.wait_for_timeout(1500)
        path = page.video.path()
        ctx.close(); browser.close()
    dest = ROOT / "public" / "demo_raw.webm"
    Path(path).replace(dest)
    (ROOT / "public" / "demo_timeline.json").write_text(json.dumps(timeline, indent=2))
    print("saved", dest, timeline)


if __name__ == "__main__":
    main()
