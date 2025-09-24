#!/usr/bin/env python3
"""
STGLAC SignUp auto-joiner (self-bootstrapping, index-based, Test vs Auto) with audit screenshots.

Parents only need Python + Google Chrome. On first run this script:
- creates a local .venv
- installs selenium + webdriver-manager
- relaunches itself inside the venv

Run:
  python stglac_autosign.py
Optional flags:
  --headless   # run Chrome headless
  --dry-run    # stop after clicking Sign Up (modal open), do not submit
  --shots-subdir NAME  # save under ./screenshots/NAME/<timestamp>
  --start-only # open group → click View → handle Continue → stop on invitation page
"""

# --- self-bootstrap: create .venv, install deps, relaunch inside it ---
import os, sys, subprocess, venv
NEEDED = ("selenium", "webdriver-manager")

def _have_needed() -> bool:
    try:
        import importlib
        for m in NEEDED:
            importlib.import_module(m)
        return True
    except Exception:
        return False

if os.environ.get("STGLAC_BOOTSTRAPPED") != "1":
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    if not _have_needed():
        if not os.path.isdir(venv_dir):
            venv.EnvBuilder(with_pip=True).create(venv_dir)
        py = os.path.join(venv_dir, "Scripts" if os.name == "nt" else "bin", "python")
        # Install/upgrade pip and required packages
        subprocess.check_call([py, "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([py, "-m", "pip", "install", "selenium", "webdriver-manager"])
        # Relaunch inside venv
        env = dict(os.environ)
        env["STGLAC_BOOTSTRAPPED"] = "1"
        os.execve(py, [py, __file__, *sys.argv[1:]], env)
# --- end self-bootstrap ---

import argparse
import re
import time
from datetime import datetime
from typing import Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os as _os  # after bootstrap; used by Snapper

# ---------- Config ----------
GROUP_URL = "https://signup.com/group/581591834043"
INVITATION_URL_HINT = "signup.com/client/invitation2"
PARENT_DUTIES_ENTRY_ID = "9140767160102"  # Stable entry id for Parent Duties card

POLL_SECS = 30          # group page poll interval for "View"
MAX_POLL_MINUTES = 30   # max time to wait for "View"
WAIT = 20               # explicit wait (seconds)
SHORT = 5

# ---------- Full 62-item EVENT MAP (index = row number shown to parent) ----------
EVENT_MAP: Dict[int, str] = {
  1:"Ground Setup — 4:30–5:45",
  2:"Hurdle Setup — 4:45–~6:00",
  3:"Long Jump Setup — 4:30–5:30",
  4:"Track Setup — 4:30–5:30",
  5:"Canteen Setup — 5:15–6:15",
  6:"Canteen BBQ Cook — 5:15–6:15",
  7:"Canteen BBQ Cook — 6:15–7:15",
  8:"Canteen BBQ Cook — 7:15–8:15",
  9:"Canteen Server — 5:15–6:45",
 10:"Canteen Server — 6:45–7:45",
 11:"Canteen Server — 7:45–8:30",
 12:"CT Clip Bd Marshal — 5:55–7:45",
 13:"CT Finish Line Marshal — 5:25–End",
 14:"CT Finish Line Recorder — 5:25–End",
 15:"CT Recorder Trainee — 5:25–End",
 16:"CT Start Line Recorder — 5:25–7:45",
 17:"CT Starter (trainee) — 5:25–End",
 18:"CT Track Referee — 5:55–7:45",
 19:"Discus 1 (9G/11G/11B) — 6:00–End",
 20:"Discus 2 (14s/SEN) — 6:00–End",
 21:"Discus 3 (6B/7G-1) — 6:15–End",
 22:"Discus 4 (6G/7G-2) — 6:15–End",
 23:"HJ Scissor 1 (9G/9B) — 5:30–6:30",
 24:"HJ Scissor 2 (9G/9B) — 5:30–6:30",
 25:"High Jump-1 (12B/13B) — 6:00–End",
 26:"High Jump-2 (12G/13G) — 6:00–End",
 27:"Jav-1 (SEN/11B/14s) — 6:15–7:30",
 28:"Jav-2 (11G) — 6:00–End",
 29:"LJ3/TJ3 — 5:30–End (7B-1/13B/14s)",
 30:"LJ4/TJ4 — 5:30–End (7B-2/13G/12G/SEN)",
 31:"LJ/TJ1 — 5:40–End (7G-1/6B/10G/12B)",
 32:"LJ2/TJ2 — 5:40–End (7G-2/6B/10B/11G)",
 33:"ST Clip Board Marshal — 5:55–7:45",
 34:"ST Finish Line Marshal — 5:55–7:45",
 35:"ST Finish Line Recorder — 5:55–7:45",
 36:"ST Hurdle Helpers — 5:55–7:45",
 37:"ST Start Line Recorder — 5:55–7:45",
 38:"ST Starter — 5:55–7:45",
 39:"ST Track Referee — 5:55–7:45",
 40:"Shot Put 1 (9B/10B/12B) — 5:30–End",
 41:"Shot Put 2 (8B/13G) — 5:30–End",
 42:"Shot Put 3 (8G/10G/12G/13B) — 5:30–End",
 43:"10B Age Group Assistant (5:45pm)",
 44:"10G Age Group Assistant (5:45pm)",
 45:"11B Age Group Assistant (5:45pm)",
 46:"11G Age Group Assistant (5:45pm)",
 47:"12B Age Group Assistant (5:45pm)",
 48:"12G Age Group Assistant (5:45pm)",
 49:"13B Age Group Assistant (5:45pm)",
 50:"13G Age Group Assistant (5:45pm)",
 51:"14s Age Group Assistant (5:45pm)",
 52:"15s/16s/17s Age Group Assistant (5:45pm)",
 53:"6B Age Group Assistant (5:15pm)",
 54:"6G Age Group Assistants (5:15pm)",
 55:"7B Age Group Assistant Grp1 (5:15pm)",
 56:"7B Age Group Assistant Grp2 (5:15pm)",
 57:"7G Age Group 1 Assistant (5:15pm)",
 58:"7G Age Group 2 Assistant (5:15pm)",
 59:"8B Age Group Assistant (5:15pm)",
 60:"8G Age Group Assistant (5:15pm)",
 61:"9B Age Group Assistant (5:15pm)",
 62:"9G Age Group Assistant (5:15pm)",
}

# ---------- Week-specific maps (A/B). Currently identical; can diverge later ----------
WEEK_A_EVENT_MAP: Dict[int, str] = {
  1: "#Ground Setup 4:30PM to 5:45PM",
  2: "#LJ 1/2/3/4 Setup 4:30PM - 5:30PM",
  3: "#Track Setup 4:30PM to 5:30PM",
  4: "/Canteen - Setup 5:15 - 6:15",
  5: "/Canteen BBQ Cook 5:15 - 6:15",
  6: "/Canteen BBQ Cook 6:15 - 7:15",
  7: "/Canteen BBQ Cook 7:15 - 8:15",
  8: "/Canteen Server 5:15 - 6:45",
  9: "/Canteen Server 6:45 - 7:45",
 10: "/Canteen Server 7:45 - 8:30",
 11: "CT - Clip Board Marshal - 5:55 till End",
 12: "CT - Finish Line Marshalls 5:25 till end",
 13: "CT - Finish Line Recorder 5:25 till End",
 14: "CT - Start Line Recorder 5:55 till End",
 15: "CT - Starter 5:25 till end",
 16: "CT - Track Referee - 5:55pm till end",
 17: "Discus 1: 5:30pm - 7:00pm (8B/12G/12B)",
 18: "Discus 1: 7:00 - End (10G/13G)",
 19: "Discus 2: 5:55 - End (10G/10B/9B/8G/13G)",
 20: "Discus 3: 5:25 - End (8G/7B-1/13B)",
 21: "Discus 4: 6:15 - 7:00pm (7B-2)",
 22: "HJ Scissors-1 (10G/10B) 5:55 - End",
 23: "HJ Scissors-2 (10G/10B) 5:55pm - End",
 24: "HJ-1 (11B/SENs/11G) 5:55pm - End",
 25: "HJ-2 (11B/14s/11G) 5:55pm - End",
 26: "Javelin 1 (13B) 7:00pm - End",
 27: "Javelin 1 (13G/12G) 5:55pm - 7:00pm",
 28: "Javelin 2 (12B) 5:55pm - 6:45pm",
 29: "LJ/TJ 1 5:30PM till End (9G/8B/11G)",
 30: "LJ/TJ 2 5:30pm till End (9G/8G/11B)",
 31: "LJ/TJ 3 5:30pm till End (9B/14s/13G/12B)",
 32: "LJ/TJ 4 5:30pm till End (9B/SEN/13B/12G)",
 33: "ST - Clip Board Marshal 5:25 till End",
 34: "ST - Finish Line Marshal 5:25 till End",
 35: "ST - Finish Line Recorder 5:25 till End",
 36: "ST - Start Line Marshal 5:25 till End",
 37: "ST - Start Line Recorder 5:25 till End",
 38: "ST - Starter 5:25 till End",
 39: "ST - Track Referee 5:25 till End",
 40: "Shot Put 1 5:55pm - End (11G/11B/SEN)",
 41: "Shot Put 2 7:30pm - End (9G/14s)",
 42: "Shot Put 3 6:30 - 7:30 (9G)",
 43: "Shot Put TT 2 5:45 - End (6G/7G-2)",
 44: "Shot Put TT-1 5:45 - 6:45 (6B/7G-1)",
 45: "_10B Age Group Assistant (5:45pm)",
 46: "_10G Age Group Assistant (5:45pm)",
 47: "_11B Age Group Assistant (5:45pm)",
 48: "_11G Age Group Assistant (5:45pm)",
 49: "_12B Age Group Assistant (5:45pm)",
 50: "_12G Age Group Assistant (5:45pm)",
 51: "_13G Age Group Assistant (5:45pm)",
  52: "_14s Age Group Assistant (5:45pm)",
  53: "_15s/16s/17s Age Group Assistant (5:45pm)",
  54: "_6B Age Group Assistants (5:15pm)",
  55: "_6G Age Group Assistants (5:15pm)",
  56: "_7B-1 Age Group Assistant (5:15pm)",
  57: "_7B-2 Age Group Assistant (5:15pm)",
  58: "_7G-1 Age Group Assistant (5:15pm)",
  59: "_7G-2 Age Group Assistant (5:15pm)",
  60: "_8B Age Group Assistant (5:15pm)",
  61: "_8G Age Group Assistant (5:15pm)",
  62: "_9B Age Group Assistant (5:15pm)",
  63: "_9G Age Group Assistant (5:15pm)",
}
WEEK_B_EVENT_MAP: Dict[int, str] = dict(EVENT_MAP)

# ---------- Utils ----------
class Snapper:
    def __init__(self, base_dir: str | None = None):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = base_dir or _os.path.join(".", "screenshots")
        self.dir = _os.path.join(base, ts)
        _os.makedirs(self.dir, exist_ok=True)
        self.n = 0
    def shot(self, driver, label: str):
        self.n += 1
        path = _os.path.join(self.dir, f"{self.n:02d}_{label}.png")
        try:
            driver.save_screenshot(path)
            print(f"[snap] {path}")
        except Exception as e:
            print(f"[snap] failed: {e}")

def build_driver(headless: bool):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1400,1800")
    else:
        opts.add_argument("--start-maximized")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def wait_exist(driver, xp, timeout=WAIT):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xp)))

def wait_click(driver, xp, timeout=WAIT):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    el.click()
    return el

def click_any(driver, xps: List[str], timeout=WAIT) -> bool:
    for xp in xps:
        try:
            wait_click(driver, xp, timeout)
            return True
        except Exception:
            pass
    return False

def exist_any(driver, xps: List[str], timeout=SHORT) -> bool:
    for xp in xps:
        try:
            wait_exist(driver, xp, timeout)
            return True
        except Exception:
            pass
    return False

# ---------- Group page: poll 'View' only ----------
def handle_view_button_only(driver, snap: Snapper) -> bool:
    """
    Stay on the group page and poll until the orange 'View' button is clickable,
    then click it. No other entry paths are used.
    """
    driver.get(GROUP_URL)
    time.sleep(2)
    snap.shot(driver, "group_loaded")

    # Prefer clicking the Parent Duties link by its stable entry id if present
    try:
        pd_link = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
            By.XPATH,
            f"//a[contains(@href, '/login/entry/{PARENT_DUTIES_ENTRY_ID}')]"
        )))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pd_link)
        snap.shot(driver, "group_parent_duties_link_visible")
        pd_link.click()
        snap.shot(driver, "group_parent_duties_link_clicked")
        WebDriverWait(driver, WAIT).until(EC.url_contains(INVITATION_URL_HINT))
        return True
    except Exception:
        # Try navigating directly to the secure invitation URL as a fallback
        try:
            direct_url = f"https://signup.com/client/invitation2/secure/{PARENT_DUTIES_ENTRY_ID}/false"
            driver.get(direct_url)
            snap.shot(driver, "group_parent_duties_direct_nav")
            WebDriverWait(driver, WAIT).until(EC.url_contains(INVITATION_URL_HINT))
            return True
        except Exception:
            pass

    VIEW_XPATHS = [
        # Target the Parent Duties card by its title/link text, then find its View button
        "//a[contains(., 'Parent Duties') or contains(., 'Parent Duty') or contains(., 'Parent Duties Week')]/ancestor::div[.//button[@data-i18n='View' or contains(., 'View')]][1]//button[@data-i18n='View' or contains(., 'View')]",
        # Alt: search any element containing Parent Duties text and pick a descendant View button
        "(//*[contains(normalize-space(.), 'Parent Duties') or contains(normalize-space(.), 'Parent Duties Week')]//button[@data-i18n='View' or contains(., 'View')])[1]",
        # Fallback: the second visible 'View' (Parent Duties typically second card)
        "(//button[@data-i18n='View' or contains(., 'View')])[2]",
        # Generic fallbacks
        "//div[contains(@class,'form-row') and contains(@class,'button')]//button[@data-i18n='View']",
        "//div[contains(@class,'form-row') and contains(@class,'button')]//button[contains(., 'View')]",
        "//button[@data-i18n='View']",
        "//button[contains(., 'View')]",
        "//a[contains(., 'View')]",
    ]

    deadline = time.time() + MAX_POLL_MINUTES * 60
    while time.time() < deadline:
        for xp in VIEW_XPATHS:
            try:
                el = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                snap.shot(driver, "group_view_visible")
                el.click()
                snap.shot(driver, "group_view_clicked")
                WebDriverWait(driver, WAIT).until(EC.url_contains(INVITATION_URL_HINT))
                return True
            except Exception:
                pass
        print(f"[poll] 'View' not visible/clickable yet… retrying in {POLL_SECS}s")
        time.sleep(POLL_SECS)
        driver.refresh()
    return False

# ---------- Invitation page utilities ----------
def handle_continue_as_if_present(driver, snap: Snapper):
    try:
        if exist_any(driver, ["//span[@data-i18n='ConfirmEmailContinueAs']"], timeout=3):
            snap.shot(driver, "continue_as_modal_seen")
            btn = "//button[.//span[@data-i18n='ConfirmEmailContinueAs']]"
            wait_click(driver, btn, timeout=WAIT)
            snap.shot(driver, "continue_as_clicked")
            WebDriverWait(driver, WAIT).until_not(EC.presence_of_element_located((By.XPATH, btn)))
    except Exception:
        pass

def ensure_day_expanded(driver, snap: Snapper):
    try:
        snap.shot(driver, "invitation_list_initial")
        # Keep clicking "Show more spots" until it no longer appears
        while True:
            try:
                btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//*[self::button or self::a][@data-i18n='_OverflowMoreJobs_' or contains(@class,'vsl-orangebtn') or contains(normalize-space(.), 'Show more spots')]"
                )))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                snap.shot(driver, "show_more_spots_visible")
                txt_before = driver.page_source
                btn.click()
                # wait briefly for list to grow / button to re-render
                time.sleep(0.6)
            except Exception:
                break
        # Expand the current day if collapsed (generic selectors)
        clicked = click_any(driver, [
            "//div[contains(@class,'dayRow') and contains(@class,'collapsed')]",
            "//button[contains(@class,'day') and contains(@class,'expand')]",
        ], timeout=3)
        if clicked:
            time.sleep(0.5)
            snap.shot(driver, "day_expanded")
    except Exception:
        pass

def uncheck_hide_full_spots_if_checked(driver, snap: Snapper):
    try:
        lbl = driver.find_element(By.XPATH, "//label[contains(.,'Hide Full Spots')]")
        cb = lbl.find_element(By.XPATH, ".//input[@type='checkbox']")
        if cb.is_selected():
            (lbl or cb).click()
            time.sleep(0.3)
            snap.shot(driver, "hide_full_spots_unchecked")
    except Exception:
        pass

def uncheck_show_my_spots_only_if_checked(driver, snap: Snapper):
    try:
        lbl = driver.find_element(By.XPATH, "//label[contains(.,'Show My Spots Only')]")
        cb = lbl.find_element(By.XPATH, ".//input[@type='checkbox']")
        if cb.is_selected():
            (lbl or cb).click()
            time.sleep(0.3)
            snap.shot(driver, "show_my_spots_unchecked")
    except Exception:
        pass

def collect_event_actions(driver):
    """
    Return a DOM-ordered list of visible assignment rows with their action button and title.
    Each item: {"index": i, "row": WebElement, "btn": WebElement, "title": str}
    """
    rows = driver.find_elements(By.XPATH, "//div[contains(@class,'assignment-widget')]")
    actions = []
    idx = 0
    for row in rows:
        # Find the action control (Sign Up / Full) within the row
        try:
            btn = row.find_element(
                By.XPATH,
                ".//*[self::button or self::a]"
                "[normalize-space()='SIGN UP' or contains(.,'Sign Up') or "
                " normalize-space()='Full' or normalize-space()='FULL']"
            )
        except Exception:
            continue
        try:
            if not row.is_displayed():
                continue
        except Exception:
            pass
        idx += 1
        try:
            title_el = row.find_element(By.XPATH, ".//a[contains(@class,'title') or contains(@class,'SpotTitle')]")
            title = title_el.text
        except Exception:
            title = row.text
        actions.append({"index": idx, "row": row, "btn": btn, "title": title})
    return actions

def is_signup_button(btn) -> bool:
    try:
        txt = (btn.text or "").lower()
        cls = (btn.get_attribute("class") or "").lower()
        return ("sign up" in txt) and btn.is_enabled() and ("disabled" not in cls)
    except Exception:
        return False

# ---------- Identify / Confirm / Participant form ----------
def identify_and_confirm(driver, snap: Snapper, email: str):
    # Identify modal
    snap.shot(driver, "identify_modal_open")
    email_x = ["//input[@type='email']", "//input[contains(@placeholder,'@')]", "//input[contains(@class,'email')]"]
    for xp in email_x:
        try:
            el = wait_exist(driver, xp); el.clear(); el.send_keys(email); break
        except Exception:
            pass
    else:
        snap.shot(driver, "identify_email_not_found")
        raise RuntimeError("Email input not found on Identify modal.")
    snap.shot(driver, "identify_email_filled")
    if not click_any(driver, ["//button[contains(.,'Continue')]", "//a[contains(.,'Continue')]"]):
        snap.shot(driver, "identify_continue_missing")
        raise RuntimeError("Continue button not found on Identify modal.")

    # Confirm modal
    snap.shot(driver, "confirm_modal_open")
    if not click_any(driver, ["//button[contains(.,'Confirm')]", "//a[contains(.,'Confirm')]"]):
        snap.shot(driver, "confirm_button_missing")
        raise RuntimeError("Confirm button not found.")
    snap.shot(driver, "confirm_clicked")

def fill_participant_form(driver, snap: Snapper, name: str, email: str, phone: str, bib: str,
                          confirm_before_save: bool, selection_text: str) -> bool:
    def set_field(label_contains: str, val: str):
        xp = f"//label[contains(.,'{label_contains}')]/following::*[self::input or self::textarea][1]"
        el = wait_exist(driver, xp); el.clear(); el.send_keys(val)

    snap.shot(driver, "participant_form_open")
    set_field("Name", name)
    set_field("Email", email)
    set_field("Phone", phone)
    try:
        set_field("ONE Bib", bib)
    except Exception:
        set_field("Bib", bib)
    snap.shot(driver, "participant_form_filled")

    if confirm_before_save:
        print("\n=== TEST MODE: Review selection before saving ===")
        print(selection_text)
        resp = input("Proceed to 'Save and Done'? [y/N]: ").strip().lower()
        if resp not in ("y", "yes"):
            print("Aborted before save. (Nothing submitted.)")
            snap.shot(driver, "aborted_before_save")
            return False

    if not click_any(driver, ["//button[contains(.,'Save and Done')]", "//a[contains(.,'Save and Done')]"]):
        snap.shot(driver, "save_and_done_missing")
        raise RuntimeError("Save and Done not found.")
    snap.shot(driver, "save_and_done_clicked")
    return True

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="Run Chrome headless")
    ap.add_argument("--dry-run", action="store_true",
                    help="Stop after clicking 'Sign Up' (modal open), do not submit anything.")
    ap.add_argument("--shots-subdir", default="", metavar="NAME",
                    help="Save screenshots under ./screenshots/NAME/<timestamp>.")
    ap.add_argument("--start-only", action="store_true",
                    help="Open group page, click orange 'View', handle 'Continue as…' modal, then exit on invitation page.")
    args = ap.parse_args()

    print("== STGLAC Auto Sign ==")

    # Fast smoke test for locked weeks
    if args.start_only:
        try:
            base_shots_dir = _os.path.join(".", "screenshots", args.shots_subdir) if args.shots_subdir else _os.path.join(".", "screenshots")
            snap = Snapper(base_dir=base_shots_dir)
            driver = build_driver(args.headless)
            if not handle_view_button_only(driver, snap):
                print("[error] Timed out waiting for the orange 'View' button.")
                return
            handle_continue_as_if_present(driver, snap)
            snap.shot(driver, "start_only_invitation_page")
            print("[start-only] Reached invitation page. Exiting.")
        except Exception as e:
            print(f"[exception] {e}")
            snap.shot(driver, "start_only_exception")
        finally:
            time.sleep(3)
        return
    # Choose mode
    def ask(prompt, ok):
        while True:
            s = input(prompt).strip()
            if ok(s): return s
            print("  -> Please try again.")

    # Week selection first
    week = ask("Week: [A] or [B] : ", lambda s: s.strip().upper() in ("A","B"))
    week = week.strip().upper()

    mode = ask("Mode: [1] Test (confirm before save)  [2] Auto : ",
               lambda s: s in ("1","2"))
    test_mode = (mode == "1")

    # Choose the week's map
    ACTIVE_MAP = WEEK_A_EVENT_MAP if week == "A" else WEEK_B_EVENT_MAP

    print("\nPick up to 3 event numbers (comma-separated) from:")
    for k in range(1, len(ACTIVE_MAP)+1):
        print(f"  {k:02d}: {ACTIVE_MAP[k]}")

    name  = ask("\nYour full name: ", lambda s: len(s) > 1)
    email = ask("Email: ", lambda s: "@" in s and "." in s)
    phone = ask("Phone: ", lambda s: len(re.sub(r'\D+','', s)) >= 6)
    bib   = ask("Bib number: ", lambda s: len(s) > 0)

    def parse_prefs(raw: str) -> List[int]:
        out, seen = [], set()
        for p in raw.split(","):
            p = p.strip()
            if p.isdigit():
                n = int(p)
                if 1 <= n <= len(ACTIVE_MAP) and n not in seen:
                    out.append(n); seen.add(n)
        return out[:3]

    prefs = parse_prefs(ask("Preferred events (e.g. 36,38,35): ",
                            lambda s: len(parse_prefs(s)) > 0))
    print(f"> preferences: {prefs}\n")

    # Now open Chrome after collecting inputs
    base_shots_dir = _os.path.join(".", "screenshots", args.shots_subdir) if args.shots_subdir else _os.path.join(".", "screenshots")
    snap = Snapper(base_dir=base_shots_dir)
    driver = build_driver(args.headless)

    try:
        # 1) Group page: wait for and click the orange "View"
        if not handle_view_button_only(driver, snap):
            print("[error] Timed out waiting for the orange 'View' button.")
            return

        # 2) Invitation page: handle dialogs/filters
        handle_continue_as_if_present(driver, snap)
        if INVITATION_URL_HINT not in driver.current_url:
            print(f"[warn] Invitation URL not detected (ok if embedded): {driver.current_url}")

        ensure_day_expanded(driver, snap)
        uncheck_hide_full_spots_if_checked(driver, snap)
        uncheck_show_my_spots_only_if_checked(driver, snap)

        # 3) Collect rows and step by index
        snap.shot(driver, "preference_index_mode_list")
        actions = collect_event_actions(driver)
        if not actions:
            print("[result] No assignment rows found. (Filters? Day collapsed?)")
            snap.shot(driver, "no_assignment_rows")
            return
        print(f"[info] Detected {len(actions)} assignment rows.")

        chosen = None
        chosen_title = ""
        for n in prefs:
            i = n - 1
            if i < 0 or i >= len(actions):
                print(f"[skip] Preference #{n} is out of range (we see {len(actions)} rows).")
                continue

            item = actions[i]
            row, btn, title = item["row"], item["btn"], (item["title"] or "").strip()
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)
            snap.shot(driver, f"pref_{n:02d}_row")

            if is_signup_button(btn):
                print(f"[select] Preference #{n} is AVAILABLE — “{title[:80]}”. Clicking Sign Up…")
                snap.shot(driver, f"pref_{n:02d}_before_click")
                btn.click()
                snap.shot(driver, f"pref_{n:02d}_clicked")
                chosen = n
                chosen_title = title
                break
            else:
                print(f"[full] Preference #{n} is currently FULL — “{title[:80]}”. Trying next…")

        if not chosen:
            # Offer interactive fallback: show available rows and let user pick one
            available = [it for it in actions if is_signup_button(it["btn"])]
            if not available:
                print("[result] None of your preferences are available right now.")
                snap.shot(driver, "no_preference_available")
                return

            print("\n[choice] Your preferences are full. Available SIGN UP rows:")
            for it in available:
                print(f"  {it['index']:02d}: {it['title']}")

            while True:
                pick = input("Pick an available number (or press Enter to cancel): ").strip()
                if pick == "":
                    print("Cancelled by user. No action taken.")
                    snap.shot(driver, "user_cancel_after_full")
                    return
                if pick.isdigit():
                    num = int(pick)
                    match = next((it for it in available if it["index"] == num), None)
                    if match is not None:
                        row, btn = match["row"], match["btn"]
                        title = (match["title"] or "").strip()
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)
                        snap.shot(driver, f"manual_pick_{num:02d}_before_click")
                        btn.click()
                        snap.shot(driver, f"manual_pick_{num:02d}_clicked")
                        chosen = num
                        chosen_title = title
                        break
                print("  -> Invalid choice. Please pick one of the listed numbers or press Enter.")

        if args.dry_run:
            print("[dry-run] stopping with sign-up modal open.")
            snap.shot(driver, "dry_run_modal_open")
            return

        # 4) Identify → Confirm → Participant form
        identify_and_confirm(driver, snap, email)

        selection_text = (f"\nSelection\n"
                          f"- Preference #: {chosen}\n"
                          f"- Week: {week}\n"
                          f"- Event label (your list): {ACTIVE_MAP.get(chosen, 'N/A')}\n"
                          f"- Page title: {chosen_title}\n"
                          f"- Name: {name}\n- Email: {email}\n- Phone: {phone}\n- Bib: {bib}\n")

        saved = fill_participant_form(
            driver, snap, name, email, phone, bib,
            confirm_before_save=test_mode,
            selection_text=selection_text
        )
        if not saved:
            return

        time.sleep(2)
        snap.shot(driver, "final_state")
        print("✓ Completed sign-up.")

    except Exception as e:
        print(f"[exception] {e}")
        snap.shot(driver, "exception")
    finally:
        time.sleep(5)

if __name__ == "__main__":
    main()
