import re
import os
import time
import logging
import traceback
import pandas as pd

from datetime import datetime
from dateutil import parser

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc


# ============================================================
# CONFIG
# ============================================================
RUN_HEADLESS = True
OUTPUT_FILE = "output.csv"

PAGES = [
    (
        "https://watfordpalacetheatre.co.uk/whats-on/?category=musical",
        "Musical"
    ),
    (
        "https://watfordpalacetheatre.co.uk/whats-on/?category=drama",
        "Play"
    ),
]


# ============================================================
# LOGGING
# ============================================================
if not os.path.exists("log"):
    os.makedirs("log")

logging.basicConfig(
    filename="log/scrape.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def log(msg, level="info"):

    print(msg)

    if level == "error":
        logging.error(msg)

    elif level == "warning":
        logging.warning(msg)

    else:
        logging.info(msg)


# ============================================================
# BROWSER
# ============================================================
def setup_browser():

    log("=" * 80)
    log("SETTING UP BROWSER")

    options = uc.ChromeOptions()

    if RUN_HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(
        options=options,
        version_main=147
    )

    log("Browser started successfully")
    log("=" * 80)

    return driver


# ============================================================
# SAFE GET
# ============================================================
def safe_get(driver, url, retries=3):

    for attempt in range(1, retries + 1):

        try:

            log(f"Loading URL ({attempt}/{retries})")
            log(url)

            driver.get(url)

            log("Page loaded successfully")

            return True

        except Exception as e:

            log(
                f"Page load failed: {e}",
                "error"
            )

            time.sleep(2)

    return False


# ============================================================
# SCROLL
# ============================================================
def scroll_to_load_all(driver):

    log("Scrolling page...")

    last_height = driver.execute_script(
        "return document.body.scrollHeight"
    )

    while True:

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(2)

        new_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if new_height == last_height:
            break

        last_height = new_height

    log("Finished scrolling page")


# ============================================================
# DATE PARSER
# ============================================================
def parse_date_range(text):

    try:

        text = text.strip()

        parts = re.split(
            r"\s*[-–—]\s*",
            text
        )

        # ----------------------------------------------------
        # SINGLE DATE
        # ----------------------------------------------------
        if len(parts) == 1:

            parsed = parser.parse(
                parts[0]
            ).strftime("%Y-%m-%d")

            return parsed, parsed

        # ----------------------------------------------------
        # DATE RANGE
        # ----------------------------------------------------
        elif len(parts) == 2:

            open_date = parts[0].strip()
            close_date = parts[1].strip()

            close_parts = close_date.split()
            open_parts = open_date.split()

            # 12 Jan - 15 March 2025
            if len(open_parts) == 2:

                year = close_parts[-1]

                open_date = (
                    f"{open_date} {year}"
                )

            # 12 - 15 March 2025
            elif len(open_parts) == 1:

                month = close_parts[1]
                year = close_parts[2]

                open_date = (
                    f"{open_date} {month} {year}"
                )

            parsed_open = parser.parse(
                open_date
            ).strftime("%Y-%m-%d")

            parsed_close = parser.parse(
                close_date
            ).strftime("%Y-%m-%d")

            return parsed_open, parsed_close

        else:

            raise ValueError(
                f"Unexpected date format: {text}"
            )

    except Exception as e:

        log(
            f"Date parse error: {text} | {e}",
            "error"
        )

        return None, None


# ============================================================
# EXTRACT EVENTS
# ============================================================
def extract_events(driver, category):

    log("=" * 80)
    log(f"EXTRACTING EVENTS | CATEGORY: {category}")

    events = []

    cards = driver.find_elements(
        By.CSS_SELECTOR,
        "div.gridblock.postitem"
    )

    log(f"Found {len(cards)} event cards")

    for idx, card in enumerate(cards, start=1):

        try:

            title = card.find_element(
                By.CSS_SELECTOR,
                "h2.entry-title"
            ).text.strip()

            url = card.find_element(
                By.CSS_SELECTOR,
                "a"
            ).get_attribute("href")

            if not url.startswith("http"):
                continue

            date_text = card.find_element(
                By.CSS_SELECTOR,
                "h2.entry-date"
            ).text.strip()

            # ------------------------------------------------
            # CURRENCY
            # ------------------------------------------------
            currency = None

            try:

                info_text = card.find_elements(By.TAG_NAME, "p")
                currency_text = " ".join([p.get_attribute("textContent").strip()
                for p in info_text if p.get_attribute("textContent").strip()])

                if "£" in currency_text:
                    currency = "GBP"

                elif "$" in currency_text:
                    currency = "USD"

                elif "€" in currency_text:
                    currency = "EUR"

                elif "₦" in currency_text:
                    currency = "NGN"

            except Exception as e:

                log(
                    f"Currency extraction failed: {e}",
                    "warning"
                )

            open_d, close_d = parse_date_range(
                date_text
            )

            events.append({

                "title": title,
                "venue_url": url,
                "category": category,
                "open_date": open_d,
                "close_date": close_d,
                "currency": currency

            })

            log(f"[{idx}] Extracted: {title}")
            log(f"Currency: {currency}")

        except Exception as e:

            log(
                f"Event extraction failed: {e}",
                "error"
            )

            log(
                traceback.format_exc(),
                "error"
            )

    log(f"Total extracted events: {len(events)}")

    return events


# ============================================================
# EXTRACT EVENT DETAILS
# ============================================================
def extract_event_details(
    driver,
    open_date=None,
    close_date=None
):

    log("=" * 80)
    log("EXTRACTING EVENT DETAILS")

    data = {

        "upcoming_performances": [],
        "seat_pricing": {},

        "venue": None,
        "address": None,
        "city": None,
        "country": None,

        "venue_capacity": None,

        "is_limited_run": False
    }

    performances = []

    # --------------------------------------------------------
    # VENUE
    # --------------------------------------------------------
    try:

        footer = driver.find_element(
            By.CSS_SELECTOR,
            "p.footeraddress"
        )

        lines = [
            x.strip()
            for x in footer.text.split("\n")
            if x.strip()
        ]

        if lines:

            data["venue"] = (
                lines[0]
                .replace(",", "")
                .strip()
            )

            if len(lines) > 1:

                parts = [
                    p.strip()
                    for p in lines[1].split(",")
                ]

                if len(parts) > 0:
                    data["address"] = parts[0]

                if len(parts) > 1:
                    data["city"] = parts[1]

            if ".co.uk" in driver.current_url:
                data["country"] = "United Kingdom"

        log(f"Venue: {data['venue']}")

    except Exception as e:

        log(
            f"Venue extraction failed: {e}",
            "warning"
        )

    # --------------------------------------------------------
    # PERFORMANCES
    # --------------------------------------------------------
    try:

        blocks = driver.find_elements(
            By.CSS_SELECTOR,
            "div.spektrix_booking--event"
        )

        log(f"Found {len(blocks)} performances")

        for block in blocks:

            try:

                date_text = block.find_element(
                    By.CSS_SELECTOR,
                    ".spektrix_booking--date"
                ).text.strip()

                time_text = block.find_element(
                    By.CSS_SELECTOR,
                    ".spektrix_booking--time"
                ).text.strip()

                parsed_date = parser.parse(
                    date_text,
                    fuzzy=True
                ).strftime("%Y-%m-%d")

                parsed_time = parser.parse(
                    time_text,
                    fuzzy=True
                ).strftime("%H:%M")

                performances.append({

                    "date": parsed_date,
                    "time": parsed_time

                })

            except Exception as e:

                log(
                    f"Performance parse failed: {e}",
                    "warning"
                )

        data["upcoming_performances"] = performances

    except Exception as e:

        log(
            f"Performance extraction failed: {e}",
            "error"
        )

    # --------------------------------------------------------
    # LIMITED RUN
    # --------------------------------------------------------
    try:

        if open_date and close_date:

            open_dt = parser.parse(open_date)
            close_dt = parser.parse(close_date)

            run_days = (
                close_dt - open_dt
            ).days

            performance_count = len(performances)

            data["is_limited_run"] = (

                run_days <= 21
                or performance_count <= 10

            )

            log(
                f"Limited run: {data['is_limited_run']}"
            )

    except Exception as e:

        log(
            f"Limited run calculation failed: {e}",
            "warning"
        )

    # --------------------------------------------------------
    # BOOK BUTTON
    # --------------------------------------------------------
    try:

        log("Clicking booking button...")

        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    "a.button"
                )
            )
        )

        driver.execute_script(
            "arguments[0].click();",
            btn
        )

        time.sleep(5)

    except Exception as e:

        log(
            f"Booking button failed: {e}",
            "warning"
        )

        return data

    # --------------------------------------------------------
    # IFRAME
    # --------------------------------------------------------
    try:

        iframe = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.ID,
                    "SpektrixIFrame"
                )
            )
        )

        driver.switch_to.frame(iframe)

        time.sleep(3)

        log("Inside booking iframe")

    except Exception as e:

        log(
            f"Iframe failed: {e}",
            "warning"
        )

        return data

    # --------------------------------------------------------
    # CAPACITY
    # --------------------------------------------------------
    try:

        seats = driver.find_elements(
            By.CSS_SELECTOR,
            ".SeatingArea img"
        )

        capacity = sum(

            1 for seat in seats

            if (
                seat.get_attribute("tooltip")
                or seat.get_attribute("title")
            )
        )

        data["venue_capacity"] = capacity

        log(f"Venue capacity: {capacity}")

    except Exception as e:

        log(
            f"Capacity extraction failed: {e}",
            "warning"
        )

    # --------------------------------------------------------
    # SEAT PRICING
    # --------------------------------------------------------
    try:

        seat_list = []

        seat_elements = driver.find_elements(
            By.CSS_SELECTOR,
            "img.SeatSelectable"
        )

        log(f"Found {len(seat_elements)} seats")

        for seat in seat_elements:

            try:

                tooltip = (
                    seat.get_attribute("tooltip")
                    or seat.get_attribute("title")
                    or ""
                )

                match = re.search(
                    r"([A-Z]+\d+)\s*-\s*.*?([\d,.]+)",
                    tooltip
                )

                if not match:
                    continue

                seat_code = match.group(1)

                ticket_price = float(
                    match.group(2).replace(",", "")
                )

                seat_list.append({

                    "seat": seat_code,
                    "ticket_price": ticket_price

                })

            except Exception as e:

                log(
                    f"Seat parse failed: {e}",
                    "warning"
                )

        # ----------------------------------------------------
        # BUILD PERFORMANCE MAP
        # ----------------------------------------------------
        seat_pricing = {}

        for perf in performances:

            perf_key = (
                f"{perf['date']} "
                f"{perf['time']}"
            )

            seat_pricing[perf_key] = seat_list

        data["seat_pricing"] = seat_pricing

        log(
            f"Seat pricing performances: "
            f"{len(seat_pricing)}"
        )

    except Exception as e:

        log(
            f"Seat pricing extraction failed: {e}",
            "error"
        )

    finally:

        driver.switch_to.default_content()

        log("Returned to main page")

    return data


# ============================================================
# MAIN SCRAPER
# ============================================================
def scrape_shows():

    start_time = time.time()

    log("=" * 80)
    log("SCRAPER STARTED")
    log("=" * 80)

    driver = setup_browser()

    all_rows = []

    total_success = 0
    total_failed = 0

    try:

        for page_num, (url, category) in enumerate(
            PAGES,
            start=1
        ):

            log("=" * 80)
            log(
                f"PAGE {page_num}/{len(PAGES)}"
            )

            log(f"CATEGORY: {category}")

            if not safe_get(driver, url):

                total_failed += 1
                continue

            scroll_to_load_all(driver)

            events = extract_events(
                driver,
                category
            )

            log(
                f"Processing {len(events)} events"
            )

            for idx, e in enumerate(events, start=1):

                try:

                    log("=" * 80)
                    log(
                        f"EVENT {idx}/{len(events)}"
                    )

                    log(f"TITLE: {e['title']}")

                    if not safe_get(
                        driver,
                        e["venue_url"]
                    ):

                        total_failed += 1
                        continue

                    time.sleep(2)

                    details = extract_event_details(

                        driver,

                        open_date=e["open_date"],
                        close_date=e["close_date"]

                    )

                    row = {

                        "title": e["title"],
                        "venue_url": e["venue_url"],
                        "category": category,

                        "venue": details["venue"],
                        "address": details["address"],
                        "city": details["city"],
                        "country": details["country"],

                        "open_date": e["open_date"],
                        "close_date": e["close_date"],

                        "booking_start_date": None,
                        "booking_end_date": None,

                        "upcoming_performances": str(
                            details[
                                "upcoming_performances"
                            ]
                        ),

                        "capacity": details[
                            "venue_capacity"
                        ],

                        "currency": e["currency"],

                        "is_limited_run": details[
                            "is_limited_run"
                        ],

                        "seat_pricing": str(
                            details[
                                "seat_pricing"
                            ]
                        ),

                        "scrape_datetime": datetime.now().strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    }

                    all_rows.append(row)

                    total_success += 1

                    log(
                        f"SUCCESSFULLY SCRAPED: "
                        f"{e['title']}"
                    )

                except Exception as e:

                    total_failed += 1

                    log(
                        f"Event failed: {e}",
                        "error"
                    )

                    log(
                        traceback.format_exc(),
                        "error"
                    )

        # ----------------------------------------------------
        # REMOVE DUPLICATES
        # ----------------------------------------------------
        log("=" * 80)
        log("REMOVING DUPLICATES")

        unique = {

            (r["title"], r["venue"]): r

            for r in all_rows
        }

        final = list(unique.values())

        log(f"Final rows: {len(final)}")

        # ----------------------------------------------------
        # DATAFRAME
        # ----------------------------------------------------
        log("Creating dataframe...")

        df = pd.DataFrame(final)

        # ----------------------------------------------------
        # FORCE COLUMN ORDER
        # ----------------------------------------------------
        columns = [

            "title",
            "venue_url",
            "category",

            "venue",
            "address",
            "city",
            "country",

            "open_date",
            "close_date",

            "booking_start_date",
            "booking_end_date",

            "upcoming_performances",

            "capacity",

            "currency",

            "is_limited_run",

            "seat_pricing",

            "scrape_datetime"
        ]

        df = df[columns]

        # ----------------------------------------------------
        # SAVE CSV
        # ----------------------------------------------------
        df.to_csv(
            OUTPUT_FILE,
            index=False
        )

        log("=" * 80)
        log(f"CSV SAVED: {OUTPUT_FILE}")

        log(f"SUCCESS COUNT: {total_success}")
        log(f"FAILED COUNT: {total_failed}")

        elapsed = round(
            time.time() - start_time,
            2
        )

        log(f"TOTAL RUNTIME: {elapsed} seconds")

    finally:

        driver.quit()

        log("=" * 80)
        log("BROWSER CLOSED")
        log("SCRAPER FINISHED")
        log("=" * 80)


# ============================================================
# START
# ============================================================
if __name__ == "__main__":

    scrape_shows()

