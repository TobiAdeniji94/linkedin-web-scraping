"""
LinkedIn Jobs scraper (handles 'Sign in to view more jobs' modal)

- Env creds: LINKEDIN_USER, LINKEDIN_PASS   (optionally via .env)
- Selenium Manager (no driver path)
- Robust selectors + explicit waits
- Detects + clears 'Sign in to view more jobs' overlay by re-authing
- Parameterized search; CSV includes job_description
"""

from __future__ import annotations

import os
import time
import argparse
import logging
from typing import Optional, Dict, List

# Optional .env for dev
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


# ----------------------------- CLI / Config ----------------------------- #

def get_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape LinkedIn job postings.")
    p.add_argument("--keywords", default="junior data analyst")
    p.add_argument("--location", default="Spain")
    p.add_argument("--geoId", default="105646813")
    p.add_argument("--pages", type=int, default=13)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--out", default="job_offers.csv")
    return p.parse_args()

def get_credentials() -> tuple[str, str]:
    u, pw = os.getenv("LINKEDIN_USER"), os.getenv("LINKEDIN_PASS")
    if not u or not pw:
        raise RuntimeError("Set LINKEDIN_USER and LINKEDIN_PASS (env or .env).")
    return u, pw

def build_search_url(keywords: str, location: str, geo_id: Optional[str]) -> str:
    from urllib.parse import urlencode, quote_plus
    base = "https://www.linkedin.com/jobs/search/"
    params = {"keywords": keywords, "location": location}
    if geo_id: params["geoId"] = geo_id
    return f"{base}?{urlencode(params, quote_via=quote_plus)}"


# ----------------------------- Browser ---------------------------------- #

def make_driver(headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,1200")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-logging")
    # (Optionally reduce bot fingerprinting; use responsibly)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
    except Exception:
        pass
    return driver


# ----------------------------- Utils ------------------------------------ #

def try_click(driver: webdriver.Chrome, wait: WebDriverWait, by: By, sel: str, timeout: int = 5) -> bool:
    try:
        elem = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, sel)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
        elem.click()
        return True
    except Exception:
        return False

def first_text(scope: webdriver.Chrome | WebElement, selectors: List[tuple[By, str]], timeout: int = 6) -> Optional[str]:
    for by, sel in selectors:
        try:
            elem = WebDriverWait(scope, timeout).until(EC.presence_of_element_located((by, sel)))
            txt = elem.text.strip()
            if txt: return txt
        except Exception:
            continue
    return None


# ----------------------------- Auth ------------------------------------- #

def login(driver: webdriver.Chrome, wait: WebDriverWait, user: str, pwd: str) -> None:
    driver.get("https://www.linkedin.com/login")
    # Best-effort cookie/consent dismissal (varies by region)
    for sel in [
        "//button[.//span[contains(., 'Accept') or contains(., 'Agree')]]",
        "//button[contains(., 'Accept')]",
        "//button[contains(., 'I agree')]",
        "button[aria-label*='cookie']",
        "button[aria-label*='Cookie']",
        "button[title*='Accept']",
    ]:
        if try_click(driver, wait, By.XPATH, sel, 2) or try_click(driver, wait, By.CSS_SELECTOR, sel, 2):
            break
    wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(user)
    wait.until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(pwd)
    try_click(driver, wait, By.XPATH, "//button[@type='submit']", 10)

def is_authwall_modal(driver: webdriver.Chrome) -> bool:
    # Look for the specific modal text or generic artdeco modal
    try:
        h = driver.find_elements(By.XPATH, "//h2[contains(., 'Sign in to view more jobs')]")
        if h: return True
    except Exception:
        pass
    try:
        modals = driver.find_elements(By.CSS_SELECTOR, ".artdeco-modal, .sign-in-modal")
        return len(modals) > 0
    except Exception:
        return False

def clear_signin_overlay_or_reauth(driver: webdriver.Chrome, wait: WebDriverWait,
                                   search_url: str, user: str, pwd: str, attempts: int = 1) -> None:
    """
    If 'Sign in to view more jobs' overlay is present:
      - click 'Sign in' to go to /login
      - perform login
      - return to search_url
    Else:
      - try dismiss (X) or ESC
    """
    if not is_authwall_modal(driver):
        return

    # Try close (X) first
    for sel in ["button[aria-label='Dismiss']", "button[aria-label='Close']", ".artdeco-modal__dismiss"]:
        if try_click(driver, wait, By.CSS_SELECTOR, sel, 2):
            time.sleep(0.5)
            if not is_authwall_modal(driver):
                return

    # Fall back: click "Sign in" inside modal and log in
    clicked = try_click(driver, wait, By.XPATH, "//button[contains(., 'Sign in')]", 5)
    if not clicked:
        # Sometimes it's an <a>
        clicked = try_click(driver, wait, By.XPATH, "//a[contains(., 'Sign in')]", 5)

    if clicked:
        # Complete login then return to search
        login(driver, wait, user, pwd)
        driver.get(search_url)
        time.sleep(1.0)
        # Recheck once
        if attempts > 0 and is_authwall_modal(driver):
            clear_signin_overlay_or_reauth(driver, wait, search_url, user, pwd, attempts - 1)
    else:
        # Try ESC as last resort
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass


# ----------------------------- Results ---------------------------------- #

def _find_results_container(driver: webdriver.Chrome, wait: WebDriverWait) -> Optional[WebElement]:
    candidates = [
        "ul.jobs-search__results-list",
        ".jobs-search-results__list",
        "div.jobs-search-two-pane__results-list",
        "[data-test-reusables-search__results-list]",
        "[data-test-search-results] ul",
    ]
    for sel in candidates:
        try:
            return WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
        except TimeoutException:
            continue
    return None

def collect_links(driver: webdriver.Chrome, wait: WebDriverWait, pages: int) -> List[str]:
    links: set[str] = set()

    def harvest() -> None:
        container = _find_results_container(driver, wait)
        if not container:
            snippet = (driver.page_source or "")[:1500].replace("\n", " ")
            logging.error("No results list. URL=%s | Snippet=%s", driver.current_url, snippet)
            raise TimeoutException("Jobs results container not found.")
        anchors = []
        anchors += container.find_elements(By.CSS_SELECTOR, "a[href*='/jobs/view/']")
        anchors += container.find_elements(By.CSS_SELECTOR, "li a[data-job-id]")
        anchors += container.find_elements(By.CSS_SELECTOR, "a.job-card-container__link")
        for a in anchors:
            href = (a.get_attribute("href") or "").strip()
            if href.startswith("https://www.linkedin.com/jobs/view"):
                links.add(href.split("?")[0])

    # Page 1
    harvest()
    logging.info("Collected %d links on page 1", len(links))

    # Page 2..N
    for page in range(2, max(2, pages + 1)):
        clicked = False
        for sel in [
            f"button[aria-label='Page {page}']",
            f"li.artdeco-pagination__indicator button[aria-label='Page {page}']",
        ]:
            try:
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                btn.click()
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            logging.warning("Could not navigate to page %d; stopping pagination.", page)
            break
        time.sleep(1.2)
        harvest()
        logging.info("Collected %d total links after page %d", len(links), page)

    return list(links)


# ----------------------------- Job page --------------------------------- #

def scrape_job(driver: webdriver.Chrome, wait: WebDriverWait, url: str) -> Optional[Dict[str, Optional[str]]]:
    try:
        driver.get(url)
        try_click(driver, wait, By.CSS_SELECTOR, ".show-more-less-html__button", 4)
        try_click(driver, wait, By.CSS_SELECTOR, ".artdeco-card__actions button", 3)

        top = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-unified-top-card")))

        title = first_text(top, [(By.CSS_SELECTOR, "h1"), (By.CSS_SELECTOR, ".jobs-unified-top-card__job-title")])
        company = first_text(top, [(By.CSS_SELECTOR, "a.jobs-unified-top-card__company-name"),
                                   (By.CSS_SELECTOR, ".jobs-unified-top-card__company-name")])
        location = first_text(top, [(By.CSS_SELECTOR, ".jobs-unified-top-card__bullet"),
                                    (By.CSS_SELECTOR, "[data-test-topcard-location]")])
        workplace = first_text(top, [(By.CSS_SELECTOR, ".jobs-unified-top-card__workplace-type")])
        posted = first_text(top, [(By.CSS_SELECTOR, ".jobs-unified-top-card__posted-date"),
                                  (By.CSS_SELECTOR, "[data-test-posted-date]")])
        schedule = first_text(top, [(By.CSS_SELECTOR, ".jobs-unified-top-card__job-insight")])

        desc_container = driver.find_elements(By.CSS_SELECTOR, ".jobs-description__content .jobs-box__html-content")
        description = desc_container[0].text.strip() if desc_container else None

        if not title and not description:
            return None

        return {
            "job_title": title,
            "company_name": company,
            "company_location": location,
            "work_method": workplace,
            "post_date": posted,
            "work_time": schedule,
            "job_description": description,
            "url": url,
        }
    except TimeoutException:
        logging.warning("Timeout while scraping %s", url)
        return None
    except Exception as e:
        logging.exception("Error scraping %s: %s", url, e)
        return None


# ----------------------------- Main ------------------------------------- #

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    args = get_args()
    user, pwd = get_credentials()
    search_url = build_search_url(args.keywords, args.location, args.geoId)

    driver = make_driver(headless=args.headless)
    wait = WebDriverWait(driver, 20)

    records: List[Dict[str, Optional[str]]] = []
    try:
        # Ensure we are authenticated
        login(driver, wait, user, pwd)

        # Go to search and handle the sign-in overlay if it appears
        driver.get(search_url)
        logging.info("Opened search: %s", search_url)
        time.sleep(1.0)
        clear_signin_overlay_or_reauth(driver, wait, search_url, user, pwd)

        # Now collect links
        links = collect_links(driver, wait, pages=args.pages)
        logging.info("Found %d unique job links", len(links))

        for idx, link in enumerate(links, start=1):
            rec = scrape_job(driver, wait, link)
            if rec:
                records.append(rec)
            time.sleep(0.6)
            if idx % 10 == 0:
                logging.info("Scraped %d/%d jobs…", idx, len(links))

        if records:
            pd.DataFrame(records).to_csv(args.out, index=False)
            logging.info("Wrote %d rows to %s", len(records), args.out)
        else:
            logging.warning("No records scraped; nothing to write.")
    finally:
        driver.quit()
        logging.info("Browser closed.")


if __name__ == "__main__":
    main()
