import re
import os
import time
import logging
import pandas as pd

from datetime import datetime
from dateutil import parser

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import undetected_chromedriver as uc


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
RUN_HEADLESS = True
OUTPUT_FILE = "output1.csv"

PAGES = [
    ("https://watfordpalacetheatre.co.uk/whats-on/?category=musical", "Musical"),
    ("https://watfordpalacetheatre.co.uk/whats-on/?category=drama", "Play"),
]

if not os.path.exists("log"):
    os.makedirs("log")

logging.basicConfig(
    filename="log/scrape.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ------------------------------------------------------------
# MAIN SCRAPER
# ------------------------------------------------------------
def scrape_shows():

    def log(msg):
        print(msg)
        logging.info(msg)

    # --------------------------------------------------------
    # BROWSER
    # --------------------------------------------------------
    def setup_browser():
        options = uc.ChromeOptions()

        if RUN_HEADLESS:
            options.add_argument("--headless=new")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        return uc.Chrome(options=options, version_main=148)

    # --------------------------------------------------------
    # SAFE GET
    # --------------------------------------------------------
    def safe_get(driver, url, retries=3):
        for _ in range(retries):
            try:
                driver.get(url)
                return True
            except:
                time.sleep(2)
        return False

    # --------------------------------------------------------
    # SCROLL
    # --------------------------------------------------------
    def scroll_to_load_all(driver):
        last = driver.execute_script("return document.body.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            new = driver.execute_script("return document.body.scrollHeight")
            if new == last:
                break
            last = new

    # --------------------------------------------------------
    # DATE PARSER
    # --------------------------------------------------------
    def parse_date_range(text):
        try:
            parts = re.split(r"\s*[-–—]\s*", text.strip())

            if len(parts) == 1:
                d = parser.parse(parts[0]).strftime("%Y-%m-%d")
                return d, d

            return (
                parser.parse(parts[0]).strftime("%Y-%m-%d"),
                parser.parse(parts[1]).strftime("%Y-%m-%d"),
            )
        except:
            return None, None

    # --------------------------------------------------------
    # LISTING PAGE
    # --------------------------------------------------------
    def extract_events(driver, category):
        events = []

        cards = driver.find_elements(By.CSS_SELECTOR, "div.gridblock.postitem")

        for card in cards:
            try:
                title = card.find_element(By.CSS_SELECTOR, "h2.entry-title").text
                url = card.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                date_text = card.find_element(By.CSS_SELECTOR, "h2.entry-date").text

                open_d, close_d = parse_date_range(date_text)

                events.append({
                    "title": title,
                    "venue_url": url,
                    "category": category,
                    "open_date": open_d,
                    "close_date": close_d
                })

            except:
                continue

        return events

    # ------------------------------------------------------------
    # DETAIL PAGE SCRAPER (FIXED)
    # ------------------------------------------------------------
    def extract_event_details(driver):

        data = {
            "upcoming_performances": [],
            "seat_pricing": {}
        }

        # -------------------------
        # PERFORMANCE EXTRACTION
        # -------------------------
        try:
            blocks = driver.find_elements(By.CSS_SELECTOR, "div.spektrix_booking--event")

            performances = []

            for b in blocks:
                try:
                    date = parser.parse(
                        b.find_element(By.CSS_SELECTOR, ".spektrix_booking--date").text,
                        fuzzy=True
                    ).strftime("%Y-%m-%d")

                    time_ = parser.parse(
                        b.find_element(By.CSS_SELECTOR, ".spektrix_booking--time").text,
                        fuzzy=True
                    ).strftime("%H:%M")

                    performances.append(f"{date} {time_}")

                except:
                    continue

            data["upcoming_performances"] = performances

        except:
            pass

        # fallback key if no performance found
        perf_key = performances[0] if performances else "unknown"

        # -------------------------
        # CLICK BOOK BUTTON
        # -------------------------
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.button"))
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)
        except:
            return data

        # -------------------------
        # SWITCH IFRAME
        # -------------------------
        try:
            iframe = driver.find_element(By.ID, "SpektrixIFrame")
            driver.switch_to.frame(iframe)
        except:
            return data

        # -------------------------
        # SEAT PRICING (FIXED FORMAT)
        # -------------------------
        seat_pricing = {}

        try:
            seats = driver.find_elements(By.CSS_SELECTOR, "img.SeatSelectable")

            seat_list = []

            for seat in seats:
                tooltip = seat.get_attribute("tooltip") or seat.get_attribute("title")

                if tooltip and "£" in tooltip:
                    try:
                        code, price = tooltip.split(" - ")
                        price_val = float(re.sub(r"[^\d.]", "", price))

                        seat_list.append({
                            "seat": code.strip(),
                            "ticket_price": price_val
                        })

                    except:
                        continue

            seat_pricing[perf_key] = seat_list

        except:
            pass

        data["seat_pricing"] = seat_pricing

        return data

    # --------------------------------------------------------
    # RUN DRIVER
    # --------------------------------------------------------
    driver = setup_browser()
    all_rows = []

    try:
        for url, category in PAGES:

            log(f"Scraping category: {category}")

            safe_get(driver, url)
            scroll_to_load_all(driver)

            events = extract_events(driver, category)

            for e in events:

                safe_get(driver, e["venue_url"])
                time.sleep(2)

                details = extract_event_details(driver)

                row = {
                    "title": e["title"],
                    "venue_url": e["venue_url"],
                    "category": category,
                    "venue": "Watford Palace Theatre",
                    "address": "20 Clarendon Road",
                    "city": "Watford",
                    "country": "UK",
                    "open_date": e["open_date"],
                    "close_date": e["close_date"],
                    "upcoming_performances": str(details["upcoming_performances"]),
                    "seat_pricing": str(details["seat_pricing"]),
                    "currency": "GBP",
                    "is_limited_run": False,
                    "scrape_datetime": datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                all_rows.append(row)

        # remove duplicates
        unique = {(r["title"], r["venue"]): r for r in all_rows}
        final = list(unique.values())

        df = pd.DataFrame(final)
        df.to_csv(OUTPUT_FILE, index=False)

        log(f"Saved {len(df)} rows to {OUTPUT_FILE}")

    finally:
        driver.quit()
        log("Browser closed")


if __name__ == "__main__":
    scrape_shows()
