# USAGE: python downloader.py phosphor
# python downloader.py <configuration_name>

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

# --- Load configuration ---
def load_config(family_name):
    config_file = f"configuration_{family_name}.json"
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    with open(config_file, "r") as f:
        config = json.load(f)
    return config


# --- Scraper ---
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


# --- Download logic ---
def compile_icon_regex(icon_types):
    type_alt = "|".join(re.escape(t) for t in icon_types)
    return re.compile(rf"/icons/(\d+)/([a-z0-9_]+?)(?:_({type_alt}))?_icon$", re.IGNORECASE)


session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
})


def download_icon(link, icon_dir, icon_re, remove_prefix):
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

    time.sleep(random.uniform(2.0, 5.0))
    ok_svg = _fetch_to_file(svg_url, svg_path)
    ok_png = _fetch_to_file(png_url, png_path)

    if ok_svg or ok_png:
        print(f"✅ Downloaded {base_name}/{icon_type} (svg:{ok_svg}, png:{ok_png})")
    else:
        print(f"❌ Failed downloads for {base_name}/{icon_type}")

    time.sleep(random.uniform(0.3, 1.2))


# --- Main ---
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

    for link in links:
        download_icon(link, icon_dir, icon_re, remove_prefix)
