import os
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random

TARGET_URL = "https://www.iconfinder.com/search?q=phosphor"
LINK_CSS = "a[data-action='icon-details'][href*='/icons/']"

SCROLL_PAUSE_TIME = 3
MAX_SCROLLS = 10000
HEADLESS_MODE = True

ICON_DIR = "icons"
ICON_TYPES = ["duotone", "light", "fill", "thin", "bold"]
LINKS_FILE = "links.txt"   # cache file

# --- Scraper ---
def scrape_icon_links(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if HEADLESS_MODE:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    print(f"Navigating to {url}...")

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, LINK_CSS))
    )

    all_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    for scroll_count in range(1, MAX_SCROLLS + 1):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, LINK_CSS)) > len(all_links)
            )
        except:
            pass

        elements = driver.find_elements(By.CSS_SELECTOR, LINK_CSS)
        for el in elements:
            href = el.get_attribute("href")
            if href:
                if href.startswith("/"):
                    href = f"https://www.iconfinder.com{href}"
                all_links.add(href)

        print(f"Scroll {scroll_count}: {len(all_links)} links collected")

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("*** Reached end of page ***")
            break
        last_height = new_height

    driver.quit()
    return sorted(all_links)


# --- Download logic ---
TYPE_ALT = "|".join(re.escape(t) for t in ICON_TYPES)
ICON_RE = re.compile(rf"/icons/(\d+)/([a-z0-9_]+?)(?:_({TYPE_ALT}))?_icon$", re.IGNORECASE)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})

def download_icon(link):
    m = ICON_RE.search(link)
    if not m:
        print(f"⚠️  Could not parse link: {link}")
        return

    icon_id = m.group(1)
    base_name = m.group(2).lower().rstrip("_")
    icon_type = m.group(3).lower() if m.group(3) else "normal"

    folder_path = os.path.join(ICON_DIR, base_name)
    os.makedirs(folder_path, exist_ok=True)

    svg_path = os.path.join(folder_path, f"{icon_type}.svg")
    png_path = os.path.join(folder_path, f"{icon_type}.png")

    if os.path.exists(svg_path) and os.path.exists(png_path):
        print(f"⏭️  Skipping existing: {base_name}/{icon_type}")
        return

    base_download_url = f"https://www.iconfinder.com/icons/{icon_id}/download"
    svg_url = f"{base_download_url}/svg/4096"
    png_url = f"{base_download_url}/png/1024"

    def _fetch_to_file(url, path, tries=5):
        if os.path.exists(path):
            return True
        for attempt in range(1, tries + 1):
            try:
                resp = session.get(url, timeout=15)
                if resp.status_code == 200 and resp.content:
                    with open(path, "wb") as fh:
                        fh.write(resp.content)
                    return True
                if resp.status_code == 429:
                    wait_time = 60 + random.uniform(10, 30)
                    print(f"⚠️ Rate limited, sleeping {wait_time:.0f}s...")
                    time.sleep(wait_time)
                    continue
                if resp.status_code == 403:
                    print(f"❌ Premium icon, skipping...")
                    break
                else:
                    print(f"Attempt {attempt}: {url} returned {resp.status_code}")
            except Exception as e:
                print(f"Attempt {attempt} error for {url}: {e}")
            time.sleep(random.uniform(2.0, 5.0))
        return False

    ok_svg = _fetch_to_file(svg_url, svg_path)
    ok_png = _fetch_to_file(png_url, png_path)

    if ok_svg or ok_png:
        print(f"✅ Downloaded {base_name}/{icon_type} (svg:{ok_svg}, png:{ok_png})")
    else:
        print(f"❌ Failed downloads for {base_name}/{icon_type}")

    time.sleep(random.uniform(0.3, 1.2))


# --- Main ---
if __name__ == "__main__":
    # 🧠 Check if links file exists
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r") as f:
            links = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(links)} links from {LINKS_FILE}")
    else:
        links = scrape_icon_links(TARGET_URL)
        with open(LINKS_FILE, "w") as f:
            for link in links:
                f.write(link + "\n")
        print(f"Saved {len(links)} links to {LINKS_FILE}")

    print(f"\n--- Total links: {len(links)} ---\n")

    for link in links:
        download_icon(link)
