import os
import re
import time
import json
import random
import requests
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
from xml.etree import ElementTree as ET

# ============================================================
# CONFIGURATION LOADER
# ============================================================
def load_config(family_name):
    config_file = f"configuration_{family_name}.json"
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r") as f:
        config = json.load(f)
    return config


# ============================================================
# SCRAPER
# ============================================================
def scrape_icon_links(url, link_css, scroll_pause_time, max_scrolls, headless_mode):
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if headless_mode:
        options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    print(f"Navigating to {url}...")

    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, link_css))
    )

    all_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    for scroll_count in range(1, max_scrolls + 1):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, link_css)) > len(all_links)
            )
        except:
            pass

        elements = driver.find_elements(By.CSS_SELECTOR, link_css)
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


# ============================================================
# DOWNLOAD + VALIDATION LOGIC
# ============================================================
def compile_icon_regex(icon_types):
    type_alt = "|".join(re.escape(t) for t in icon_types)
    return re.compile(rf"/icons/(\d+)/([a-z0-9_]+?)(?:_({type_alt}))?_icon$", re.IGNORECASE)


# ============================================================
# SESSION HANDLING (NEW)
# ============================================================
session = None
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 1
PROXIES = []  # Optional: add proxies if available


def get_new_proxy():
    if not PROXIES:
        return None
    return random.choice(PROXIES)


def reset_session():
    """Recreate the session with a new UA and (optional) proxy."""
    global session, consecutive_failures
    print("🔁 Resetting session...")
    if session:
        session.close()
    session = requests.Session()
    session.headers.update({
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{random.randint(90,120)}.0) Gecko/20100101 Firefox/{random.randint(90,120)}.0"
    })
    proxy = get_new_proxy()
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
        print(f"🌐 Using new proxy: {proxy}")
    consecutive_failures = 0
    sleep_time = random.uniform(5, 10)
    #print(f"😴 Sleeping {sleep_time/60:.1f} minutes before resuming...")
    #time.sleep(sleep_time)


# ============================================================
# VALIDATION HELPERS
# ============================================================
def check_png_corrupted(file_path):
    try:
        img = Image.open(file_path)
        img.verify()
        img = Image.open(file_path)
        img.load()
        return False
    except Exception:
        return True


def check_svg_corrupted(file_path):
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        return 'svg' not in root.tag.lower()
    except Exception:
        return True


def is_file_corrupted(file_path):
    if not os.path.exists(file_path):
        return True
    if file_path.lower().endswith(".png"):
        return check_png_corrupted(file_path)
    elif file_path.lower().endswith(".svg"):
        return check_svg_corrupted(file_path)
    return False


# ============================================================
# CORE DOWNLOAD FUNCTION
# ============================================================
def download_icon(link, icon_dir, icon_re, remove_prefix, max_retries=10):
    global consecutive_failures, session

    m = icon_re.search(link)
    if not m:
        print(f"⚠️  Could not parse link: {link}")
        return

    icon_id = m.group(1)
    base_name = m.group(2).lower().rstrip("_")
    if base_name.startswith(remove_prefix):
        base_name = base_name.replace(remove_prefix, "", 1)
    icon_type = m.group(3).lower() if m.group(3) else "normal"

    folder_path = os.path.join(icon_dir, base_name)
    os.makedirs(folder_path, exist_ok=True)

    svg_path = os.path.join(folder_path, f"{icon_type}.svg")
    png_path = os.path.join(folder_path, f"{icon_type}.png")

    if os.path.exists(svg_path) and os.path.exists(png_path):
        if not is_file_corrupted(svg_path) and not is_file_corrupted(png_path):
            print(f"⏭️  Skipping existing valid: {base_name}/{icon_type}")
            return
        else:
            print(f"⚠️ Found existing corrupted files, will re-download {base_name}/{icon_type}")
            try:
                if os.path.exists(svg_path): os.remove(svg_path)
                if os.path.exists(png_path): os.remove(png_path)
            except Exception as e:
                print(f"⚠️ Could not remove old corrupted files: {e}")

    base_download_url = f"https://www.iconfinder.com/icons/{icon_id}/download"
    svg_url = f"{base_download_url}/svg/4096"
    png_url = f"{base_download_url}/png/1024"

    def _fetch_to_file(url, path):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200 and resp.content:
                with open(path, "wb") as fh:
                    fh.write(resp.content)
                return True
            if resp.status_code == 429:
                wait_time = 5 + random.uniform(2.0, 3.0)
                print(f"⚠️ Rate limited, sleeping {wait_time:.0f}s...")
                time.sleep(wait_time)
                return False
            if resp.status_code == 403:
                print(f"❌ Premium icon, skipping...")
                return None
            print(f"⚠️ Download failed ({resp.status_code}) for {url}")
        except Exception as e:
            print(f"⚠️ Error downloading {url}: {e}")
        #time.sleep(random.uniform(2.0, 3.0))
        return False

    for attempt in range(1, max_retries + 1):
        #time.sleep(random.uniform(2.0, 3.0))

        svg_result = _fetch_to_file(svg_url, svg_path)
        png_result = _fetch_to_file(png_url, png_path)

        if svg_result is None or png_result is None:
            if os.path.exists(svg_path): os.remove(svg_path)
            if os.path.exists(png_path): os.remove(png_path)
            return

        svg_bad = is_file_corrupted(svg_path)
        png_bad = is_file_corrupted(png_path)

        if not svg_bad and not png_bad:
            consecutive_failures = 0
            print(f"✅ Downloaded {base_name}/{icon_type} (try {attempt})")
            return
        else:
            consecutive_failures += 1
            print(f"❌ Corrupted file detected on try {attempt} for {base_name}/{icon_type} "
                  f"(consecutive fails = {consecutive_failures})")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                reset_session()

            if os.path.exists(svg_path): os.remove(svg_path)
            if os.path.exists(png_path): os.remove(png_path)
            #time.sleep(random.uniform(2.0, 3.0))

    print(f"❌ Failed after {max_retries} tries: {base_name}/{icon_type}")


# ============================================================
# MAIN ENTRY
# ============================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python downloader.py <family_name>")
        sys.exit(1)

    family = sys.argv[1]
    config = load_config(family)

    target_url = config["target_url"]
    link_css = config["link_css"]
    scroll_pause_time = config["scroll_pause_time"]
    max_scrolls = config["max_scrolls"]
    headless_mode = config["headless_mode"]
    icon_dir = config["icon_dir"]
    icon_types = config["icon_types"]
    links_file = config["links_file"]
    remove_prefix = config["prefix_to_remove"]

    os.makedirs(icon_dir, exist_ok=True)
    icon_re = compile_icon_regex(icon_types)

    reset_session()  # Initialize session at start

    # Load or scrape links
    if os.path.exists(links_file):
        with open(links_file, "r") as f:
            links = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(links)} links from {links_file}")
    else:
        links = scrape_icon_links(target_url, link_css, scroll_pause_time, max_scrolls, headless_mode)
        with open(links_file, "w") as f:
            for link in links:
                f.write(link + "\n")
        print(f"Saved {len(links)} links to {links_file}")

    print(f"\n--- Total links: {len(links)} ---\n")

    for idx, link in enumerate(links, 1):
        print(f"\n[{idx}/{len(links)}] Processing: {link}")
        try:
            download_icon(link, icon_dir, icon_re, remove_prefix)
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user.")
            break
        except Exception as e:
            print(f"⚠️ Unexpected error: {e}")
            time.sleep(random.uniform(2.0, 3.0))

    print("\n✅ Done!")
