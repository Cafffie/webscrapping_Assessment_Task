import re
import os
import time
import random
import logging
import traceback
import pandas as pd

from datetime import datetime
from urllib.parse import urljoin
from dateutil import parser

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)

import undetected_chromedriver as uc


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
RUN_HEADLESS = True
BASE_URL = "https://watfordpalacetheatre.co.uk/"
OUTPUT_FILE = "output.csv"

PAGES = [
    ("https://watfordpalacetheatre.co.uk/whats-on/?category=musical", "Musical"),
    ("https://watfordpalacetheatre.co.uk/whats-on/?category=music", "Music"),
    ("https://watfordpalacetheatre.co.uk/whats-on/?category=drama", "Play"),
]

os.makedirs("log", exist_ok=True)

logging.basicConfig(
    filename="log/scrape.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# ------------------------------------------------------------
# MAIN SCRAPER
# ------------------------------------------------------------
def scrape_shows():

    def log_and_print(msg):
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
    def scroll_to_load_all_shows(driver):
        last_height = driver.execute_script("return document.body.scrollHeight")

        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    # --------------------------------------------------------
    # DATE PARSER
    # --------------------------------------------------------
    def parse_date_range(text):
        try:
            parts = re.split(r"\s*[-–—]\s*", text.strip())

            if len(parts) == 1:
                d = parser.parse(parts[0]).strftime("%Y-%m-%d")
                return d, d

            open_d = parser.parse(parts[0]).strftime("%Y-%m-%d")
            close_d = parser.parse(parts[1]).strftime("%Y-%m-%d")

            return open_d, close_d

        except:
            return None, None

    # --------------------------------------------------------
    # LISTING PAGE
    # --------------------------------------------------------
    def extract_events_from_page(driver, category):
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

    # --------------------------------------------------------
    # DETAIL PAGE + SEATS
    # --------------------------------------------------------
    def extract_event_datetime_venue(driver):

        data = {
            "upcoming_performances": [],
            "seat_pricing": {}
        }

        try:
            # ---------------------------
            # PERFORMANCE DATA
            # ---------------------------
            blocks = driver.find_elements(By.CSS_SELECTOR, "div.spektrix_booking--event")

            performances = []

            for b in blocks:
                try:
                    d = parser.parse(
                        b.find_element(By.CSS_SELECTOR, ".spektrix_booking--date").text,
                        fuzzy=True
                    ).strftime("%Y-%m-%d")

                    t = parser.parse(
                        b.find_element(By.CSS_SELECTOR, ".spektrix_booking--time").text,
                        fuzzy=True
                    ).strftime("%H:%M")

                    performances.append({"date": d, "time": t})

                except:
                    continue

            data["upcoming_performances"] = performances

            # ---------------------------
            # CLICK BOOK BUTTON
            # ---------------------------
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.button"))
                )
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(3)
            except:
                return data

            # ---------------------------
            # SWITCH TO IFRAME
            # ---------------------------
            try:
                iframe = driver.find_element(By.ID, "SpektrixIFrame")
                driver.switch_to.frame(iframe)
            except:
                return data

            # ---------------------------
            # SEAT SCRAPING
            # ---------------------------
            seat_pricing = {}

            seats = driver.find_elements(By.CSS_SELECTOR, "img.SeatSelectable, img.Seat")

            for seat in seats:
                tooltip = seat.get_attribute("tooltip") or seat.get_attribute("title")

                if tooltip and "£" in tooltip:
                    try:
                        code, price = tooltip.split(" - ")
                        seat_pricing[code.strip()] = price.strip()
                    except:
                        continue

            data["seat_pricing"] = seat_pricing

            return data

        except:
            return data

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------
    driver = setup_browser()
    all_rows = []

    try:
        for url, category in PAGES:

            print(f"\n--- CATEGORY: {category} ---")

            safe_get(driver, url)
            scroll_to_load_all_shows(driver)

            events = extract_events_from_page(driver, category)

            for e in events:

                safe_get(driver, e["venue_url"])
                time.sleep(2)

                details = extract_event_datetime_venue(driver)

                perf = details.get("upcoming_performances", [])
                seat_map = details.get("seat_pricing", {})

                row = {
                    "title": e["title"],
                    "venue_url": e["venue_url"],
                    "category": e["category"],
                    "venue": "Watford Palace Theatre",
                    "address": "20 Clarendon Road",
                    "city": "Watford",
                    "country": "UK",
                    "open_date": e["open_date"],
                    "close_date": e["close_date"],
                    "booking_start_date": None,
                    "booking_end_date": None,
                    "upcoming_performances": str(perf),
                    "capacity": None,
                    "currency": "GBP",
                    "is_limited_run": False,
                    "seat_pricing": str(seat_map),
                    "scrape_datetime": datetime.now().strftime("%Y-%m-%d %H:%M")
                }

                all_rows.append(row)

        # remove duplicates
        unique = {(r["title"], r["venue"]): r for r in all_rows}
        final = list(unique.values())

        df = pd.DataFrame(final)
        df.to_csv(OUTPUT_FILE, index=False)

        print(f"\nSaved {len(df)} rows")

    finally:
        driver.quit()
        print("Browser closed")


if __name__ == "__main__":
    scrape_shows()
