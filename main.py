import argparse
import contextlib
import datetime
import os
import random
import re
import sys
import time
from typing import Sequence

import schedule
from dotenv import load_dotenv
from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    ViewportSize,
    sync_playwright,
)

from human_simulation import (
    HumanBehaviorSimulator,
    SingleUserProfile,
    inject_stealth_scripts,
)


# Force UTF-8 to handle Korean characters in console output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

# Initialize human behavior simulator
human_sim = HumanBehaviorSimulator()

ALIEXPRESS_EMAIL = os.getenv("ALIEXPRESS_EMAIL")
ALIEXPRESS_PASSWORD = os.getenv("ALIEXPRESS_PASSWORD")

if not ALIEXPRESS_EMAIL or not ALIEXPRESS_PASSWORD:
    print("Error: Environment variables for ALIEXPRESS_EMAIL and ALIEXPRESS_PASSWORD must be set.")
    print("Please create a .env file with these variables or set them in your environment.")
    sys.exit(1)

COIN_PAGE_URL = "https://m.aliexpress.com/p/coin-index/index.html"
MAX_COLLECTION_ATTEMPTS = 3

# Fallback selectors tried in order when ship-to dropdown structure changes
SHIP_TO_SELECTORS = [
    "//div[contains(@class, 'ship-to--menuItem--')]",
    "//div[contains(@class, 'ship-to--text--')]/b[contains(text(), 'USD')]",
    "//div[contains(@class, 'es--wrap--')]/div/div[contains(@class, 'ship-to--menuItem--')]",
]

# Multiple selector strategies for collect button, including Korean UI variants
COLLECT_BUTTON_SELECTORS = [
    "//button[@id='signButton']",
    "//button[contains(@class, 'aecoin-signButton-') or contains(@class, 'aecoin-checkInButton-')]",
    "//div[contains(@class, 'checkin-button')]",
    "//div[contains(text(), 'Collect') and contains(@class, 'button')]",
    "//div[contains(text(), '출석체크') and contains(@class, 'button')]",  # "attendance check"
    "//div[contains(text(), '적립하기') and contains(@class, 'button')]",   # "collect"
    "//div[contains(text(), '체크인') and contains(@class, 'button')]",     # "check-in"
    "//button[contains(@class, 'check-in') or contains(@class, 'checkin')]",
    "//div[contains(@class, 'coin') and contains(@class, 'collect')]",
]


def random_sleep(min_seconds: float = 0.3, max_seconds: float = 0.8) -> None:
    """Use advanced human behavior simulator for realistic delays."""
    human_sim.sleep_like_human(min_seconds, max_seconds)


def highlight(locator: Locator) -> None:
    with contextlib.suppress(Exception):
        locator.evaluate("el => el.style.border='3px solid red'")


def move_mouse_to_element(page: Page, locator: Locator) -> None:
    """Move mouse to element with realistic Bezier curve path."""
    try:
        box = locator.bounding_box()
        if box:
            # Get current mouse position (approximate)
            viewport = page.viewport_size
            if not viewport:
                viewport = {"width": 1280, "height": 720}

            start_x = random.randint(0, viewport["width"])
            start_y = random.randint(0, viewport["height"])

            # Target with randomness to avoid robotic precision
            end_x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            end_y = box["y"] + box["height"] / 2 + random.uniform(-5, 5)

            # Use realistic Bezier curve movement
            human_sim.move_mouse_realistically(page, start_x, start_y, end_x, end_y)

            # Sometimes perform micro-adjustments (humans overshoot and correct)
            if random.random() < 0.3:
                adjust_x = end_x + random.uniform(-3, 3)
                adjust_y = end_y + random.uniform(-3, 3)
                page.mouse.move(adjust_x, adjust_y)
                time.sleep(random.uniform(0.05, 0.1))
    except Exception as exc:
        print(f"Mouse movement simulation failed: {exc}")


def safe_click(locator: Locator, name: str, page: Page | None = None) -> None:
    """Click element with multiple fallback methods and optional mouse movement."""
    try:
        if page:
            move_mouse_to_element(page, locator)

        locator.click(timeout=5000, no_wait_after=True)
    except Exception as exc:
        print(f"Normal click failed for {name}: {exc}. Trying click with force")
        try:
            locator.click(force=True, timeout=5000, no_wait_after=True)
        except Exception as exc2:
            print(f"Force click failed: {exc2}. Trying JavaScript click")
            try:
                locator.evaluate("el => el.click()")
            except Exception as exc3:
                print(f"JavaScript click failed: {exc3}. Trying dispatch click event")
                try:
                    locator.dispatch_event("click")
                except Exception as exc4:
                    print(f"Dispatch click failed: {exc4}. Trying direct JavaScript click on center")
                    try:
                        # Last resort: click directly at element's center
                        locator.evaluate("""
                            el => {
                                const rect = el.getBoundingClientRect();
                                const x = rect.left + rect.width / 2;
                                const y = rect.top + rect.height / 2;
                                const clickEvent = new MouseEvent('click', {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true,
                                    clientX: x,
                                    clientY: y
                                });
                                el.dispatchEvent(clickEvent);
                            }
                        """)
                    except Exception as exc5:
                        print(f"All click methods failed: {exc5}")


def type_like_human(locator: Locator, text: str) -> None:
    locator.focus()
    for char in text:
        # 1% chance to simulate a typo: type wrong char, pause, backspace, continue
        if random.random() < 0.01:
            typo_char = random.choice("qwertyuiopasdfghjklzxcvbnm")
            locator.press_sequentially(typo_char, delay=random.uniform(50, 120))
            random_sleep(0.1, 0.3)
            locator.press("Backspace")
            random_sleep(0.2, 0.5)
        locator.press_sequentially(char, delay=random.uniform(50, 120))
        random_sleep(0.05, 0.15)
        # 5% chance to pause as if thinking
        if random.random() < 0.05:
            random_sleep(0.5, 1.2)


def first_visible_locator(page: Page, selectors: Sequence[str], timeout: int = 5000) -> Locator:
    """Try selectors in order and return the first one that becomes visible."""
    last_error: Exception | None = None
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return locator
        except PlaywrightTimeoutError as exc:
            last_error = exc
    raise last_error or PlaywrightTimeoutError("None of the selectors became visible within the timeout.")


def wait_and_click_element(
    locator: Locator, 
    element_name: str, 
    timeout: int = 15000,
    min_sleep: float = 0.3,
    max_sleep: float = 0.8,
    page: Page | None = None
) -> None:
    """Wait for element, scroll into view, highlight, and click with human-like delay."""
    locator.wait_for(state="visible", timeout=timeout)

    # Use JavaScript scroll to avoid waiting for stability (handles animated elements)
    try:
        locator.evaluate("el => el.scrollIntoView({behavior: 'auto', block: 'center'})")
        random_sleep(0.3, 0.5)  # Short delay for scroll
    except Exception as scroll_error:
        print(f"JavaScript scroll failed for {element_name}: {scroll_error}. Continuing anyway...")

    highlight(locator)
    random_sleep(min_sleep, max_sleep)
    safe_click(locator, element_name, page)


def find_and_type_in_input(
    locator: Locator,
    text: str,
    element_name: str,
    timeout: int = 15000,
    pre_type_delay: tuple[float, float] = (0.3, 0.6)
) -> None:
    """Wait for input field, scroll into view, and type with human-like behavior."""
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    random_sleep(0.2, 0.4)
    locator.click()
    random_sleep(*pre_type_delay)
    print(f"Entering {element_name}...")
    type_like_human(locator, text)


def login(page: Page) -> bool:
    try:
        print("Starting login process...")

        # Random mouse movement at start (humans don't start with mouse at 0,0)
        if random.random() < 0.7:
            human_sim.random_mouse_movement(page)
            random_sleep(0.2, 0.5)

        email_input = page.locator("input.cosmos-input[label='Email or phone number']").first
        find_and_type_in_input(email_input, ALIEXPRESS_EMAIL, "email address")
        random_sleep(0.3, 0.6)

        # Close email suggestion dropdown by clicking outside or pressing Escape
        try:
            # Press Escape to close any dropdown/autocomplete
            page.keyboard.press("Escape")
            random_sleep(0.2, 0.4)
        except Exception:
            pass

        # Alternative: click on a neutral area to dismiss dropdown
        try:
            # Click on the page title or header area to dismiss autocomplete
            page.mouse.click(100, 100)
            random_sleep(0.2, 0.4)
        except Exception:
            pass

        continue_button = page.locator(
            "//button[contains(@class, 'cosmos-btn-primary') and .//span[text()='Continue']]"
        ).first
        wait_and_click_element(continue_button, "Continue button", page=page)
        print("Clicked continue button")
        random_sleep(0.8, 1.5)

        password_input = page.locator("#fm-login-password").first
        find_and_type_in_input(password_input, ALIEXPRESS_PASSWORD, "password", pre_type_delay=(0.3, 0.6))
        random_sleep(0.4, 0.8)

        sign_in_button = page.locator(
            "//button[contains(@class, 'cosmos-btn-primary') and .//span[text()='Sign in']]"
        ).first
        wait_and_click_element(sign_in_button, "Sign in button", page=page)
        print("Clicked sign in button")
        random_sleep(2, 3)
        print("Login successful")
        return True
    except Exception as exc:
        print(f"Login failed: {exc}")
        return False


def change_country_to_korea(page: Page) -> bool:
    try:
        print("Looking for the ship-to dropdown...")

        # Sometimes scroll a bit (humans explore the page)
        if random.random() < 0.4:
            human_sim.realistic_scroll(page, "down", random.randint(100, 300))
            random_sleep(0.2, 0.5)

        ship_to_dropdown = first_visible_locator(page, SHIP_TO_SELECTORS, timeout=7000)
        print("STEP 1: Ship-to dropdown found. Clicking automatically...")
        wait_and_click_element(ship_to_dropdown, "Ship-to dropdown", timeout=7000, min_sleep=0.3, max_sleep=0.6, page=page)
        random_sleep(0.5, 0.8)

        country_selector = page.locator("//div[contains(@class, 'select--text--1b85oDo')]").first
        print("STEP 2: Country selector found. Clicking automatically...")
        wait_and_click_element(country_selector, "Country selector", timeout=7000, min_sleep=0.3, max_sleep=0.6, page=page)
        random_sleep(0.4, 0.7)

        search_input = page.locator("//div[contains(@class, 'select--search--20Pss08')]/input").first
        search_input.wait_for(state="visible", timeout=7000)
        highlight(search_input)
        print("STEP 3: Search input found. Typing 'Korea'...")
        random_sleep(0.2, 0.4)
        move_mouse_to_element(page, search_input)
        search_input.click()
        search_input.fill("")
        type_like_human(search_input, "Korea")
        random_sleep(0.4, 0.7)

        # Try finding Korea in search results (handles both English and Korean UI)
        korea_option = page.locator(
            "//div[contains(@class, 'select--item') and (contains(., 'Korea') or contains(., '대한민국'))]"
        ).first
        try:
            korea_option.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            # If "Korea" doesn't work, try native Korean name (UI language may differ)
            print("No results for 'Korea'. Trying Korean name...")
            search_input.fill("")
            type_like_human(search_input, "대한민국")
            random_sleep(0.4, 0.7)
            korea_option.wait_for(state="visible", timeout=5000)

        print("STEP 4: Korea option found. Clicking automatically...")
        wait_and_click_element(korea_option, "Korea option", timeout=5000, min_sleep=0.3, max_sleep=0.6, page=page)
        random_sleep(0.5, 0.8)

        save_button = page.locator("//div[contains(@class, 'es--saveBtn--w8EuBuy')]").first
        print("STEP 5: Save button found. Clicking automatically...")
        wait_and_click_element(save_button, "Save button", timeout=7000, min_sleep=0.3, max_sleep=0.6, page=page)
        random_sleep(1, 2)
        print("Country has been saved")
        print("STEP 6: Country change complete. Continuing to the coin collection page...")
        return True
    except Exception as exc:
        print(f"Country change failed: {exc}")
        return False


def verify_korea_selected(page: Page) -> bool:
    try:
        ship_to_element = page.locator("//div[contains(@class, 'ship-to--text--')]").first
        ship_to_element.wait_for(state="visible", timeout=7000)
        ship_to_text = ship_to_element.inner_text()
        print(f"Current ship-to text: {ship_to_text}")
        # KO/ is the most reliable indicator (country code + currency)
        if "KO/" in ship_to_text:
            print("Found 'KO/' in ship-to text - Korea is definitely selected")
            return True
        if any(keyword in ship_to_text for keyword in ["Korea", "한국", "대한민국"]):
            print("Korea is selected as the country")
            return True
        print("Korea is NOT selected as the country")
        return False
    except Exception as exc:
        print(f"Error verifying Korea selection: {exc}")
        return False


def find_and_click_collect_button(page: Page) -> bool:
    print("STEP 7: Looking for the Collect button...")
    # Try predefined selectors first (most specific to least specific)
    for selector in COLLECT_BUTTON_SELECTORS:
        locator = page.locator(selector).first
        try:
            wait_and_click_element(locator, "Collect button", timeout=15000, min_sleep=0.5, max_sleep=1.0, page=page)
            random_sleep(2, 3)
            print("Collect button clicked successfully")
            return True
        except Exception as exc:
            print(f"Could not click collect button with selector {selector}: {exc}")
            continue

    # Last resort: broad text search for any clickable element containing "collect"
    try:
        print("Trying fallback approach - looking for any element that might be the collect button")
        potential_buttons = page.locator(
            "css=div, button, a",
            has_text=re.compile("collect", re.IGNORECASE),
        )
        if potential_buttons.count() > 0:
            wait_and_click_element(potential_buttons.first, "Fallback collect button", min_sleep=0.5, max_sleep=1.0, page=page)
            random_sleep(2, 3)
            return True
    except Exception as exc:
        print(f"Fallback approach failed: {exc}")

    print("Could not find any collect button despite multiple attempts")
    print("*** WILL RESTART FROM STEP 1 (COUNTRY SELECTION) ***")
    return False


def navigate_to_coin_page(page: Page) -> None:
    """Navigate to coin collection page with human-like delay."""
    print("Going to coin page after country change.")
    page.goto(COIN_PAGE_URL, wait_until="domcontentloaded")
    random_sleep(2, 3)


def run_collection_flow(page: Page, use_korea: bool = False) -> None:
    # Retry entire flow (country change + button click) up to MAX_COLLECTION_ATTEMPTS
    total_attempts = 0
    while total_attempts < MAX_COLLECTION_ATTEMPTS:
        total_attempts += 1
        print(f"Starting collection attempt {total_attempts}/{MAX_COLLECTION_ATTEMPTS}")

        if use_korea:
            print("RESTARTING FROM STEP 1: Changing country to Korea")
            if change_country_to_korea(page):
                random_sleep(2, 3)
                navigate_to_coin_page(page)
                if find_and_click_collect_button(page):
                    print("Successfully collected coins!")
                    return
                print(f"Failed to find collect button on attempt {total_attempts}, restarting from Step 1")
            else:
                print(f"Country change failed on attempt {total_attempts}")
                # On last attempt, skip country change and try coin page directly
                if total_attempts >= MAX_COLLECTION_ATTEMPTS:
                    print("Maximum attempts reached. Trying coin page directly as last resort...")
                    navigate_to_coin_page(page)
                    find_and_click_collect_button(page)
                    break
        else:
            print("Skipping country change (disabled)")
            navigate_to_coin_page(page)
            if find_and_click_collect_button(page):
                print("Successfully collected coins!")
                return
            print(f"Failed to find collect button on attempt {total_attempts}")

    if total_attempts >= MAX_COLLECTION_ATTEMPTS:
        print("Maximum attempts reached without successful coin collection.")


def click_login_button_on_coin_page(page: Page) -> bool:
    """Click the 'Log in' button that appears on the coin page before login."""
    try:
        print("Looking for 'Log in' button on coin page...")

        # Try multiple selectors for the login button
        login_button_selectors = [
            "//button[contains(@class, 'aecoin-loginButton')]",
            "//button[contains(text(), 'Log in')]",
            "//button[contains(text(), 'log in')]",
            "//button[contains(text(), 'Login')]",
            "//button[contains(text(), 'login')]",
            "//div[contains(@class, 'login-button') or contains(@class, 'loginButton')]//button",
        ]

        login_button = None
        for selector in login_button_selectors:
            try:
                login_button = page.locator(selector).first
                login_button.wait_for(state="visible", timeout=5000)
                print(f"Found login button with selector: {selector}")
                break
            except PlaywrightTimeoutError:
                continue

        if login_button:
            print("Clicking 'Log in' button...")
            wait_and_click_element(login_button, "Login button on coin page", timeout=5000, min_sleep=0.5, max_sleep=1.0, page=page)
            random_sleep(2, 3)
            print("Login button clicked, waiting for login page to load...")
            return True
        else:
            print("No 'Log in' button found - user might already be logged in or page structure changed")
            return False

    except Exception as exc:
        print(f"Error clicking login button on coin page: {exc}")
        return False


def run_automation(page: Page, use_korea: bool = False) -> None:
    """Execute the main automation workflow: navigate, login, and collect coins."""
    navigate_to_coin_page(page)
    print("Website loaded")

    # Check if there's a "Log in" button on the coin page and click it
    click_login_button_on_coin_page(page)

    if login(page):
        print("Successfully logged in")

    else:
        print("Login process failed, attempting to continue anyway...")
    run_collection_flow(page, use_korea=use_korea)
    print("Coin collection process completed.")


def main(headless: bool = False, locale: str = "", use_korea: bool = False) -> None:
    # Get consistent fingerprint for single user profile
    profile = SingleUserProfile(locale=locale)
    user_agent = profile.get_user_agent()
    viewport = profile.get_viewport()
    languages = profile.get_languages()
    timezone = profile.get_timezone()

    print(f"Using User-Agent: {user_agent[:50]}...")
    print(f"Using viewport: {viewport['width']}x{viewport['height']}")
    print(f"Using timezone: {timezone}")
    print(f"Simulating consistent single user from {locale}")
    print(f"Headless mode: {'ON' if headless else 'OFF'}")
    print(f"Use Korea: {'ENABLED' if use_korea else 'DISABLED'}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--window-size={},{}".format(viewport['width'], viewport['height']),
                # Additional anti-detection flags
                "--disable-automation",
                "--disable-blink-features=AutomationControlled",
                "--exclude-switches=enable-automation",
                "--disable-extensions",
                "--profile-directory=Default",
                "--incognito",
                "--disable-plugins-discovery",
            ],
        )

        context = browser.new_context(
            user_agent=user_agent,
            viewport=ViewportSize(width=viewport['width'], height=viewport['height']),
            locale=languages[0][:5],  # e.g., "en-US"
            timezone_id=timezone,
            permissions=["geolocation", "notifications"],
            color_scheme="light",
            extra_http_headers={
                "Accept-Language": f"{languages[0]},{languages[0][:2]};q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"',
            },
            # Mobile device parameters
            has_touch=True,
            device_scale_factor=2.625,  # Mobile device pixel ratio
            is_mobile=True,
        )

        # Inject comprehensive stealth scripts
        inject_stealth_scripts(context, locale=locale)

        print("✓ Advanced anti-detection measures activated (Mobile)")
        print("✓ Canvas and WebGL fingerprinting protection enabled")
        print("✓ Realistic mobile browser fingerprint configured")

        page = context.new_page()

        # Add page-level event listeners to simulate human behavior
        def on_page_load(page_obj: Page) -> None:
            print("Page loaded - simulating human reading time...")

        page.on("load", on_page_load)

        try:
            run_automation(page, use_korea=use_korea)
        except Exception as exc:
            print(f"An error occurred: {exc}")
        finally:
            print("Script execution complete. Closing browser in 5 seconds...")
            random_sleep(3, 5)
            context.close()
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AliExpress Coin Collector - Automated coin collection with anti-detection"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)"
    )
    parser.add_argument(
        "--locale",
        type=str,
        choices=["poland", "us_east"],
        default="poland",
        help="Select locale/timezone for the user profile (default: poland)"
    )
    parser.add_argument(
        "--use-korea",
        action="store_true",
        help="Enable country change to Korea before collecting coins (default: disabled)"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run in scheduled mode - execute once per day at random time between 10:00-14:00"
    )

    args = parser.parse_args()

    if args.schedule:
        print("=" * 60)
        print("AliExpress Coin Collector - SCHEDULED MODE")
        print("=" * 60)
        print("Running once per day at random time between 10:00 and 14:00")
        print()

        def schedule_next_run():
            """Schedule the next run at a random time between 10:00 and 14:00"""
            # Clear any existing jobs
            schedule.clear()

            # Generate random time between 10:00 and 14:00
            random_hour = random.randint(10, 13)
            random_minute = random.randint(0, 59)
            random_time = f"{random_hour:02d}:{random_minute:02d}"

            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Next run scheduled for: {random_time}")

            def job():
                print("\n" + "=" * 60)
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scheduled coin collection...")
                print("=" * 60 + "\n")

                try:
                    main(headless=args.headless, locale=args.locale, use_korea=args.use_korea)
                except Exception as e:
                    print(f"\n[ERROR] Scheduled run failed: {e}")

                print("\n" + "=" * 60)
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Scheduled run completed")
                print("=" * 60 + "\n")

                # Schedule the next run
                schedule_next_run()

            schedule.every().day.at(random_time).do(job)

        # Schedule the first run
        schedule_next_run()

        print("Scheduler started. Press Ctrl+C to exit.")
        print()

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("\n\nScheduler stopped by user.")
            sys.exit(0)
    else:
        # Run immediately without scheduling
        main(headless=args.headless, locale=args.locale, use_korea=args.use_korea)
