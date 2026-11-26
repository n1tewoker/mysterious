from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
from itertools import product

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test-artifacts"
OUT.mkdir(exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)
    def log_message(self, *a):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
Thread(target=server.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{server.server_port}/index.html"
passed = 0
failures = []
def check(condition, label):
    global passed
    assert condition, label
    passed += 1

def rect(page, selector):
    return page.locator(selector).bounding_box()

def no_overlap(a, b):
    return a["x"]+a["width"] <= b["x"]+1 or b["x"]+b["width"] <= a["x"]+1 or a["y"]+a["height"] <= b["y"]+1 or b["y"]+b["height"] <= a["y"]+1

def inside(r, w, h):
    return r is not None and r["x"] >= -1 and r["y"] >= -1 and r["x"]+r["width"] <= w+1 and r["y"]+r["height"] <= h+1

with sync_playwright() as p:
    browser = p.chromium.launch()
    for (w,h), period, topic in product([(320,568),(390,844),(844,390),(768,1024),(1280,800)], ["day","month","half"], ["general","business"]):
        name = f"{w}x{h}-{period}-{topic}"
        page = browser.new_page(viewport={"width":w,"height":h}, reduced_motion="reduce")
        page.set_default_timeout(6000)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.goto(url)
            expect(page.locator("#archie-bubble")).to_be_visible()
            check("Арчи" in page.locator("#archie-message").inner_text(), "welcome")
            bubble, mascot, ad, plus = [rect(page,x) for x in ["#archie-bubble","#archie-launch","#bottom-ad-dock","#premium-plus"]]
            check(inside(bubble,w,h) and inside(mascot,w,h), "welcome inside viewport")
            check(no_overlap(bubble,mascot) and no_overlap(bubble,ad) and no_overlap(mascot,ad) and no_overlap(mascot,plus), "no overlap")
            page.locator("#archie-close").click()
            check(not page.locator("#archie-bubble").is_visible(), "dismiss greeting")
            page.locator("#topic").select_option(topic)
            page.locator("#period").select_option(period)
            page.locator("#birth").fill("2000-02-29")
            page.locator("#question").fill("Как лучше действовать?")
            page.locator("#draw").click()
            expect(page.locator("#step-1")).to_be_visible()
            check(page.locator("#cards .card").count()==8 and page.locator("#cards .archie-explain").count()==8, "eight cards and explanations")
            check(page.locator("#month-strip button").count()==(6 if period=="half" else 0), "month navigation")
            expect(page.locator("#archie-bubble")).to_be_visible()
            page.locator("#archie-close").click()
            page.locator("#cards .archie-explain").first.click()
            expect(page.locator("#archie-bubble")).to_be_visible()
            check(len(page.locator("#archie-message").inner_text())>30, "card explanation")
            check(no_overlap(rect(page,"#archie-bubble"),rect(page,"#archie-launch")), "explanation layout")
            page.keyboard.press("Escape")
            page.locator("#to-summary").click()
            expect(page.locator("#step-2")).to_be_visible()
            page.locator("#archie-close").click()
            check(all(len(page.locator("#"+x).text_content())>30 for x in ["summaryText","favorable","caution"]), "three detailed results")
            page.locator("#favorable").locator("..").locator("summary").click()
            expect(page.locator("#archie-bubble")).to_be_visible()
            check(len(page.locator("#archie-message").inner_text())>30, "result explanation")
            page.locator("#archie-close").click()
            page.locator("#premium-plus").click()
            expect(page.locator("#account")).to_be_visible()
            check(page.locator("#premium-purchase").is_disabled() and not page.locator("#archie-bubble").is_visible(), "premium safe until configured")
            check(inside(rect(page,"#bottom-ad-dock"),w,h) and not errors, "ad and no script errors")
            if (w,h)==(390,844) and period=="half" and topic=="business":
                page.goto(url)
                page.screenshot(path=str(OUT/"mobile-archie.png"),animations="disabled")
        except Exception as exc:
            failures.append((name,str(exc)))
            page.screenshot(path=str(OUT/(name+"-failed.png")),animations="disabled")
        finally:
            page.close()
    browser.close()
server.shutdown()
print(f"Passed browser assertions: {passed}; failed scenarios: {len(failures)}")
for name, reason in failures:
    print(name,reason)
assert not failures and passed==360
