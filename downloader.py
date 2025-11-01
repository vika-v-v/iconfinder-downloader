import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

TARGET_URL = "https://www.iconfinder.com/search?q=phosphor"
LINK_CSS = "a[data-action='icon-details'][href*='/icons/']"

SCROLL_PAUSE_TIME = 2
MAX_SCROLLS = 10
HEADLESS_MODE = False

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

    # Wait for React app to render first icons
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, LINK_CSS))
    )

    all_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    for scroll_count in range(1, MAX_SCROLLS + 1):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)

        # Wait for new icons to load
        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, LINK_CSS)) > len(all_links)
            )
        except:
            pass  # maybe no new icons

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

if __name__ == "__main__":
    links = scrape_icon_links(TARGET_URL)

    print("\n--- Results ---")
    print(f"Total collected: {len(links)}\n")
    for i, link in enumerate(links[:10], 1):
        print(f"{i}. {link}")
