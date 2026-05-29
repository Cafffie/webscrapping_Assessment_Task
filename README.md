# Watford Palace Theatre Event Scraper

## Scraping structured theatre event and seating data from Watford Palace Theatre using Selenium

---

## Introduction

This project is a Python-based web scraper designed to extract structured theatre event data from the Watford Palace Theatre website.

The scraper uses Selenium with `undetected-chromedriver` to handle JavaScript-rendered pages and extract detailed production information including:

* Event titles
* Event categories
* Venue information
* Open and closing dates
* Booking windows
* Upcoming performances
* Venue capacity
* Seat-level pricing
* Currency metadata

The scraper is optimized for reliability and defensive scraping, handling dynamic booking interfaces, iframe-based seating maps, lazy-loaded pages, and inconsistent event formatting.

---

## Visual Helper (High-Level Flow)

```text
START
  |
  |--> Launch Chrome (undetected)
  |--> Open category page
        |
        |--> Scroll page to load all events
        |--> Extract event cards
              |
              |--> Open event page
                    |
                    |--> Extract venue information
                    |--> Extract performance schedule
                    |--> Detect limited-run productions
                    |--> Open booking system
                    |--> Enter booking iframe
                    |--> Extract venue capacity
                    |--> Extract seat pricing
                    |
                    |--> Save structured event record
        |
  |--> Remove duplicates
  |--> Export CSV
END
```

---

# User Instructions (How to Run)

## 1. Clone the repository

```bash
git clone https://github.com/your-repository/watford-scraper.git
cd watford-scraper
```

---

## 2. Create and activate a virtual environment (recommended)

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / Mac

```bash
python -m venv venv
source venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

### Required packages

* undetected-chromedriver
* selenium
* pandas
* python-dateutil

Optional/common support packages:

* webdriver-manager
* requests
* beautifulsoup4
* lxml
* openpyxl
* python-dotenv

---

## 4. Run the scraper

```bash
python app.py
```

---

## 5. Output

### CSV Output

The scraper generates:

```text
output.csv
```

### Logs

Execution logs are written to:

```text
log/scrape.log
```

---

# Developer Instructions (How It Works)

## Browser Setup

The scraper uses:

* `undetected_chromedriver`
* Headless Chrome support
* Automation detection bypass flags

Configuration:

```python
RUN_HEADLESS = True
```

To debug visually:

```python
RUN_HEADLESS = False
```

---

## Page Loading Strategy

The scraper uses:

* Retry-based page loading
* Infinite scroll handling
* Explicit Selenium waits
* Defensive exception handling

Function used:

```python
safe_get(driver, url)
```

---

## Event Extraction Strategy

### Category Pages

The scraper visits predefined category URLs:

```python
PAGES = [
    ("musical-url", "Musical"),
    ("drama-url", "Play")
]
```

For each category:

1. Scroll page completely
2. Locate event cards
3. Extract:

   * Title
   * Event URL
   * Date range
   * Currency
   * Category

---

## Date Parsing Logic

The scraper handles multiple formats:

Examples:

```text
12 Jan 2026
12 Jan - 15 March 2026
12 - 15 March 2026
```

Dates are normalized into:

```text
YYYY-MM-DD
```

using:

```python
dateutil.parser
```

---

## Currency Detection

Currency is inferred from page text symbols.

Supported mappings:

| Symbol | ISO Code |
| ------ | -------- |
| £      | GBP      |
| €      | EUR      |
| $      | USD      |
| ₦      | NGN      |

---

## Event Detail Extraction

Each event page is processed individually.

The scraper extracts:

### Venue Information

* Venue name
* Address
* City
* Country

---

### Performance Schedule

Extracted from booking blocks:

```python
div.spektrix_booking--event
```

Output example:

```python
[
    {
        "date": "2026-06-10",
        "time": "19:30"
    }
]
```

---

### Booking Window

Automatically calculates:

* booking_start_date
* booking_end_date

based on all discovered performances.

---

### Limited Run Detection

A production is flagged as a limited run if:

* Run duration ≤ 21 days
  OR
* Total performances ≤ 10

---

## Booking System Handling

The scraper:

1. Clicks booking button
2. Waits for iframe
3. Switches into seating iframe
4. Extracts seating information

Iframe handled:

```python
SpektrixIFrame
```

---

## Venue Capacity Extraction

Capacity is estimated from seat elements:

```python
.SeatingArea img
```

The scraper counts all valid seat entries.

---

## Seat Pricing Extraction

Seat pricing is parsed from tooltip/title attributes.

Example tooltip:

```text
A12 - Standard £35.00
```

Converted into structured format:

```python
{
  "2026-06-10 19:30": [
    {
      "seat": "A12",
      "ticket_price": 35.0
    }
  ]
}
```

---

## Final Output Structure

Each CSV row contains:

| Column                |
| --------------------- |
| title                 |
| venue_url             |
| category              |
| venue                 |
| address               |
| city                  |
| country               |
| open_date             |
| close_date            |
| booking_start_date    |
| booking_end_date      |
| upcoming_performances |
| capacity              |
| currency              |
| is_limited_run        |
| seat_pricing          |
| scrape_datetime       |

---

# Logging & Error Handling

The scraper includes:

* Retry handling
* Traceback logging
* Warning/error separation
* Defensive parsing

Log levels:

* INFO
* WARNING
* ERROR

All logs are saved to:

```text
log/scrape.log
```

---

# Contributor Expectations

If contributing to this project:

* Keep selectors defensive
* Expect HTML changes
* Minimize hardcoded waits
* Add logs for silent failures
* Avoid duplicate records
* Test booking iframe extraction thoroughly

Pull requests should include:

* What changed
* Why the fix works
* Which page types were tested

---

# Known Issues & Limitations

* Booking iframe may occasionally fail to load
* Some productions may not expose seating maps
* Seat prices may vary dynamically
* Headless mode may occasionally trigger anti-bot behavior
* Venue capacity is estimated, not official
* Page structure may change without notice

---

# Future Improvements

Potential enhancements:

* Async scraping
* MongoDB/PostgreSQL export
* Proxy rotation
* CAPTCHA solving
* Screenshot debugging
* JSON export
* Automatic schedule monitoring
* Historical pricing tracking

---

# Support the Project 💸

If this scraper helped you:

* ⭐ Star the repository
* ☕ Buy the maintainer a coffee
* 💰 Support ongoing maintenance

Scraping theatre booking systems is harder than it looks 🙂

---

Happy scraping 🚀
