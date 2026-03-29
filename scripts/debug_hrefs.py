from playwright.sync_api import sync_playwright

URL = "https://trailhead.salesforce.com/content/learn/modules/javascript-essentials-salesforce-developers"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    hrefs = page.eval_on_selector_all(
        'a[href*="/content/learn/modules/"]',
        "els => els.map(e => e.getAttribute('href'))",
    )
    print("n=", len(hrefs))
    for h in hrefs[:40]:
        print(h)
    browser.close()
