from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
import time
import json
import random
import argparse
import sys
import os
import re
import unicodedata
import logging
import ctypes


logger = logging.getLogger("linkedin_bot")
LOG_FILE = "last_run.log"

# URL fragments of the LinkedIn endpoint that actually creates an invitation.
# When you've exhausted your invite quota this endpoint answers HTTP 429
# (Too Many Requests) - sometimes WITHOUT any "limit reached" dialog in the UI.
# We watch the browser's network traffic for a 429 on these paths and stop.
INVITE_ENDPOINT_FRAGMENTS = (
    "voyagerRelationshipsDashMemberRelationships",
    "verifyQuotaAndCreate",
)

# Windows power management constants for sleep prevention
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def setup_logging(level=logging.DEBUG, log_file=LOG_FILE):
    """Configure professional logging: timestamped console + last_run.log.

    Levels used across the bot: DEBUG (verbose internals), INFO (progress),
    WARN (recoverable issues / skips) and ERROR (failures). Default visibility
    is DEBUG. The log file is opened in 'w' mode so it always contains only the
    most recent run.
    """
    logging.addLevelName(logging.WARNING, "WARN")  # show "WARN" instead of "WARNING"

    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    logger.addHandler(console)

    return logger


def _normalize_name_token(token):
    """Lowercase and strip accents so 'Júlia' and 'Julia' compare equal."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', token.lower())
        if unicodedata.category(c) != 'Mn')


# Connectors that can appear inside a compound first name (e.g. "Maria de Lourdes")
NAME_CONNECTORS = {"de", "da", "do", "das", "dos", "e"}

# Common Brazilian given names that frequently appear as the SECOND part of a
# compound first name. Stored accent-stripped and lowercase. If a person's second
# token is in this set we keep it (João + Victor); a surname (Silva, Santos...) is
# not in the set, so it is dropped (just João).
COMPOUND_GIVEN_NAMES = {
    _normalize_name_token(n) for n in [
        # masculine
        "Victor", "Vitor", "Henrique", "Eduardo", "Gabriel", "Felipe", "Miguel",
        "Lucas", "Luiz", "Luis", "Carlos", "Paulo", "Pedro", "Antonio", "Jose",
        "Augusto", "Cesar", "Otavio", "Vinicius", "Heitor", "Davi", "David",
        "Bernardo", "Arthur", "Artur", "Theo", "Benicio", "Samuel", "Isaac",
        "Gustavo", "Mateus", "Matheus", "Joao", "Ricardo", "Rodrigo", "Marcelo",
        "Marcos", "Marco", "Andre", "Alexandre", "Leonardo", "Leandro", "Fabio",
        "Bruno", "Diego", "Thiago", "Tiago", "Rafael", "Sergio", "Emanuel",
        "Enzo", "Lorenzo", "Murilo", "Nicolas", "Breno", "Caio", "Kaua", "Kauan",
        "Francisco", "Vicente", "Daniel", "Fernando", "Junior", "Filho", "Neto",
        # feminine
        "Julia", "Eduarda", "Gabriela", "Clara", "Helena", "Beatriz", "Fernanda",
        "Cristina", "Lucia", "Vitoria", "Sofia", "Sophia", "Manuela", "Alice",
        "Laura", "Leticia", "Rafaela", "Daniela", "Carolina", "Luiza", "Luisa",
        "Mariana", "Marina", "Marcela", "Juliana", "Adriana", "Patricia",
        "Priscila", "Vanessa", "Viviane", "Simone", "Sandra", "Debora", "Deborah",
        "Raquel", "Sara", "Sarah", "Tatiana", "Michele", "Michelle", "Isabel",
        "Isabela", "Isabella", "Valentina", "Cecilia", "Antonella", "Elisa",
        "Livia", "Melissa", "Yasmin", "Agatha", "Esther", "Ester", "Lais", "Lara",
        "Lourdes", "Aparecida", "Conceicao", "Regina", "Teresa", "Tereza", "Rosa",
        "Ana", "Maria", "Emanuelly", "Gabrielly", "Vitoria", "Flavia", "Camila",
        "Bianca", "Larissa", "Amanda", "Aline", "Bruna", "Carla", "Paula",
    ]
}

class LinkedInAutomator:
    def __init__(self, use_existing_browser=False, auto_continue=False, message_file="message.txt", reverse=False, no_message=False):
        """Initialize the LinkedIn Automator."""
        # Store the browser mode setting
        self.use_existing_browser = use_existing_browser
        # Store whether to auto-continue past warnings
        self.auto_continue = auto_continue
        # Store whether to navigate in reverse order (Previous instead of Next)
        self.reverse = reverse
        # Store whether to send invites without a note
        self.no_message = no_message

        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        # Enable Chrome performance logging so we can read network responses
        # (Network.responseReceived events) and detect an HTTP 429 from
        # LinkedIn's invitation endpoint - see detect_rate_limit_429().
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        if not use_existing_browser:
            # Set up a new browser instance
            self.driver = webdriver.Chrome(options=chrome_options)  # You can change to Firefox or other browsers
        else:
            # For working with an already opened browser tab
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=chrome_options)

        # Probe whether performance logging is actually available in this session.
        # When attaching to an existing browser it usually is; if not, we degrade
        # gracefully and rely on the UI-based limit detection only. This first
        # call also drains any stale network events from before the bot started.
        try:
            self.driver.get_log("performance")
            self.perf_logging = True
            logger.debug("Performance logging enabled; HTTP 429 detection active.")
        except Exception as e:
            self.perf_logging = False
            logger.warning(f"Performance logging unavailable ({type(e).__name__}): "
                           "network-level HTTP 429 detection disabled, "
                           "relying on UI limit checks only.")

        # Wait configuration
        self.wait = WebDriverWait(self.driver, 10)
        self.short_wait = WebDriverWait(self.driver, 3)

        # Load message variations from file (skipped in no-message mode).
        self.message_templates = [] if no_message else self.load_message_templates(message_file)

        # Session counters
        self.connections_sent = 0
        self.connections_failed = 0
        self.connections_skipped = 0

    # A line made up of dashes (e.g. "---") separates one message variation from
    # the next inside the message file.
    MESSAGE_SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
    DEFAULT_MESSAGE = "Hello {name}! I'd like to connect with you."

    def load_message_templates(self, file_path):
        """Load one or more message variations from a text file.

        To look less templated, the bot rotates randomly among several note
        variations. They live in the same file, separated by a line containing
        only dashes ("---"). A file with no separator is just a single variation,
        preserving the original behaviour. Each variation is trimmed and capped
        at LinkedIn's 300-char limit. Always returns a list with at least one
        template (falling back to a default), or [] in no-message mode.
        """
        try:
            # No note will be sent, so no templates are needed.
            if self.no_message or not file_path:
                return []

            if not os.path.exists(file_path):
                logger.warning(f"Message file '{file_path}' not found. Using default message.")
                return [self.DEFAULT_MESSAGE]

            with open(file_path, 'r', encoding='utf-8') as file:
                raw = file.read()

            # Split on the dashed separator line and drop empty chunks.
            variations = [v.strip() for v in self.MESSAGE_SEPARATOR.split(raw)]
            variations = [v for v in variations if v]

            if not variations:
                logger.warning("Message file is empty. Using default message.")
                return [self.DEFAULT_MESSAGE]

            # Enforce LinkedIn's 300-char cap per variation.
            cleaned = []
            for v in variations:
                if len(v) > 300:
                    v = v[:300]
                    logger.warning("A message variation exceeded 300 chars and was truncated.")
                cleaned.append(v)

            logger.info(f"Loaded {len(cleaned)} message variation(s) from '{file_path}'.")
            return cleaned

        except Exception as e:
            logger.error(f"Error loading message file: {str(e)}. Using default message.")
            return [self.DEFAULT_MESSAGE]

    @staticmethod
    def _message_length(text):
        """Count characters the way LinkedIn does: UTF-16 code units.

        LinkedIn's 300-char counter uses JavaScript string length (UTF-16), where
        an emoji like 😄 counts as 2. Counting with Python's len() (code points)
        would under-count and let the message overflow to e.g. 302/300.
        """
        return len(text.encode('utf-16-le')) // 2

    def _remove_name_placeholder(self, template):
        """Drop the {name} placeholder along with an adjacent comma/space.

        Turns "Olá, {name}!" into "Olá!" (not "Olá, !") so the greeting still
        reads cleanly when the name is omitted.
        """
        return re.sub(r",?\s*\{name\}", "", template)

    def personalize_message(self, name=None):
        """Pick a random message variation and personalize it with the name.

        The bot rotates among the variations loaded from the message file so the
        notes don't all look identical. LinkedIn caps the note at 300 characters;
        if inserting the name pushes a variation past 300 (e.g. a long compound
        name like "Walisson Henrique"), we omit the name for that invite so the
        request still goes through ("Olá!" instead of "Olá, Walisson Henrique!").
        """
        if not self.message_templates:
            return ""

        template = random.choice(self.message_templates)

        if name:
            personalized = template.replace("{name}", name)
            if self._message_length(personalized) <= 300:
                return personalized
            logger.warning(f"Message would be {self._message_length(personalized)} chars with "
                  f"the name '{name}' (limit 300). Omitting the name for this invite.")

        # No name, or the name made the message exceed 300 characters
        return self._remove_name_placeholder(template)

    def _cdp_click(self, element, description="element"):
        """Dispatch a trusted click via Chrome DevTools Protocol.

        CDP Input.dispatchMouseEvent produces events with isTrusted=true because
        they go through Chrome's native input pipeline, not JavaScript. This works
        even for elements inside shadow DOM where ActionChains sometimes fails to
        compute correct coordinates.
        """
        try:
            loc = element.location
            sz = element.size
            x = loc['x'] + sz['width'] / 2
            y = loc['y'] + sz['height'] / 2
            params = {"button": "left", "clickCount": 1, "modifiers": 0, "x": x, "y": y}
            self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {**params, "type": "mousePressed"})
            time.sleep(0.05)
            self.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {**params, "type": "mouseReleased"})
            logger.debug(f"CDP click OK on {description} at ({x:.0f},{y:.0f})")
            return True
        except Exception as e:
            logger.debug(f"CDP click failed on {description}: {type(e).__name__}: {e}")
            return False

    def _robust_click(self, element, description="element"):
        """Click an element with a TRUSTED event, retrying before any JS fallback.

        LinkedIn ignores untrusted (JS) clicks for actions like Send, so we must
        keep the click trusted. Order: native .click() -> ActionChains -> CDP
        (all three trusted) -> JS click only as a last resort (logged as a
        warning, since it may be ignored). Returns True if some click was
        dispatched.
        """
        # 1) Native click (trusted)
        try:
            element.click()
            logger.debug(f"Native click OK on {description}")
            return True
        except Exception as e:
            logger.debug(f"Native click failed on {description} "
                         f"({type(e).__name__}: {e}); trying ActionChains")

        # 2) ActionChains click (trusted real mouse event via OS)
        try:
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", element)
            except Exception:
                pass
            ActionChains(self.driver).move_to_element(element).pause(0.1).click().perform()
            logger.debug(f"ActionChains click OK on {description}")
            return True
        except Exception as e:
            logger.debug(f"ActionChains failed on {description} "
                         f"({type(e).__name__}: {e}); trying CDP click")

        # 3) CDP click (trusted via Chrome DevTools Protocol; bypasses shadow DOM
        #    coordinate issues that can trip up ActionChains)
        if self._cdp_click(element, description):
            return True

        # 4) Last resort: untrusted JS click
        logger.warning(f"All trusted clicks failed on {description}; "
                       f"falling back to JS click - LinkedIn may ignore it")
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e2:
            logger.warning(f"All click methods failed on {description}: {e2}")
            return False

    def fill_message_box(self, message_box, text):
        """Type the personalized note into the modal textarea reliably.

        LinkedIn's "Send" button stays disabled until the framework registers
        real input. Setting the value purely via JS often fails to enable it, so
        we type with real keystrokes (which also updates the 0/300 counter).
        ChromeDriver's send_keys cannot handle non-BMP characters (e.g. emoji),
        so when the text contains any, we type the BMP part to activate the
        binding and then inject the full text (with emoji) via the textarea's
        native value setter plus an input event.
        """
        # Focus the field with a real click so the framework treats it as user input
        try:
            message_box.click()
        except Exception:
            self.driver.execute_script("arguments[0].focus();", message_box)

        message_box.clear()

        bmp_text = ''.join(ch for ch in text if ord(ch) <= 0xFFFF)

        if bmp_text == text:
            # Pure BMP text: real keystrokes enable Send and update the counter
            message_box.send_keys(text)
            return

        # Mixed content with emoji/non-BMP: type the BMP part first to activate
        # the framework's input binding, then set the full value via JS.
        if bmp_text:
            message_box.send_keys(bmp_text)
        self.driver.execute_script(
            "const el = arguments[0], val = arguments[1];"
            "const setter = Object.getOwnPropertyDescriptor("
            "window.HTMLTextAreaElement.prototype, 'value').set;"
            "setter.call(el, val);"
            "el.dispatchEvent(new Event('input', { bubbles: true }));"
            "el.dispatchEvent(new Event('change', { bubbles: true }));",
            message_box, text)

    def get_modal_shadow_root(self, timeout=10):
        """Return the #interop-outlet shadow root once the invite modal is inside it.

        LinkedIn now renders the connect/invite modal inside an open Shadow DOM
        host (<div id="interop-outlet" data-testid="interop-shadowdom">). Selenium
        cannot reach shadow content with XPath or top-level find_element, so every
        modal interaction must go through this shadow root (CSS selectors only).
        Returns the ShadowRoot, or None if the modal never appeared.
        """
        end = time.time() + timeout
        while time.time() < end:
            for host_sel in ("#interop-outlet", "[data-testid='interop-shadowdom']"):
                hosts = self.driver.find_elements(By.CSS_SELECTOR, host_sel)
                for host in hosts:
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    try:
                        if sr.find_elements(
                                By.CSS_SELECTOR,
                                "[data-test-modal-id='send-invite-modal'], "
                                "[data-test-modal] [id='send-invite-modal']"):
                            return sr
                    except Exception:
                        continue
            time.sleep(0.3)
        return None

    def find_in_shadow(self, shadow_root, css, timeout=10, require_enabled=False):
        """Wait for and return a visible element matching css inside a shadow root.

        ShadowRoot only supports CSS selectors (not XPath). When require_enabled is
        True we wait until the element is also enabled (e.g. the Send button, which
        stays disabled until the note text is registered). Returns None on timeout.
        """
        end = time.time() + timeout
        while time.time() < end:
            try:
                for el in shadow_root.find_elements(By.CSS_SELECTOR, css):
                    try:
                        if el.is_displayed() and (not require_enabled or el.is_enabled()):
                            return el
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(0.3)
        return None

    def wait_modal_closed(self, shadow_root, timeout=5):
        """Return True once the invite modal is no longer present in the shadow root."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                if not shadow_root.find_elements(
                        By.CSS_SELECTOR, "[data-test-modal-id='send-invite-modal']"):
                    return True
            except Exception:
                return True  # shadow/host gone => modal closed
            time.sleep(0.3)
        return False

    def modal_requires_email(self, shadow_root):
        """Detect the 'enter their email to connect' verification screen.

        Some members can only be invited if you supply their email address. That
        screen replaces the normal note/Send flow with an email input. We can't
        provide the email, so the caller cancels and moves on.
        """
        try:
            return bool(shadow_root.find_elements(
                By.CSS_SELECTOR,
                "input[type='email'], input[name='email'], "
                "[data-test-send-invite-modal-check-email-link]"))
        except Exception:
            return False

    def dismiss_open_modal(self):
        """Best-effort close of any open invite modal (shadow DOM first, then light)."""
        try:
            for host_sel in ("#interop-outlet", "[data-testid='interop-shadowdom']"):
                for host in self.driver.find_elements(By.CSS_SELECTOR, host_sel):
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    btns = sr.find_elements(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                    if btns:
                        self._robust_click(btns[0])
                        return
        except Exception:
            pass
        try:
            btns = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Dismiss')]")
            if btns:
                self.driver.execute_script("arguments[0].click();", btns[0])
        except Exception:
            pass

    def check_invitation_limit_warning(self):
        """Check if the invitation limit warning is displayed and ask user what to do."""
        try:
            # First check for the HARD LIMIT reached dialog - always stop for this
            hard_limit_elements = self.driver.find_elements(
                By.XPATH,
                "//h2[contains(text(), 'reached the weekly invitation limit')] | " +
                "//h2[@id='ip-fuse-limit-alert__header' and contains(text(), 'reached the weekly')] | " +
                "//div[contains(@class, 'ip-fuse-limit-alert')]//h2[contains(text(), 'reached')]"
            )

            if hard_limit_elements:
                logger.error("You've reached the weekly invitation limit! Stopping automation.")

                # Click the "Got it" button to dismiss the warning
                try:
                    got_it_button = self.driver.find_element(
                        By.XPATH,
                        "//button[.//span[text()='Got it']] | " +
                        "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]"
                    )
                    self.driver.execute_script("arguments[0].click();", got_it_button)
                except:
                    # Try to dismiss the dialog if the "Got it" button can't be found
                    try:
                        dismiss_button = self.driver.find_element(
                            By.XPATH,
                            "//button[@aria-label='Dismiss']"
                        )
                        self.driver.execute_script("arguments[0].click();", dismiss_button)
                    except:
                        pass

                return False  # Always stop when hard limit is reached

            # Then check for the "close to" warning
            warning_elements = self.driver.find_elements(
                By.XPATH,
                "//h2[contains(text(), 'close to the weekly invitation limit')] | " +
                "//div[contains(@class, 'ip-fuse-limit-alert')]//h2[contains(text(), 'close to')]"
            )

            if warning_elements:
                logger.warning("You're close to the weekly invitation limit!")

                if self.auto_continue:
                    logger.info("Auto-continue enabled (-y flag). Automatically continuing past the warning.")
                    # Click the "Got it" button to dismiss the warning
                    got_it_button = self.driver.find_element(
                        By.XPATH,
                        "//button[.//span[text()='Got it']] | " +
                        "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]"
                    )
                    self.driver.execute_script("arguments[0].click();", got_it_button)
                    time.sleep(1)
                    return True
                else:
                    # Ask the user what they want to do
                    user_decision = input("\nDo you want to continue and use some of your remaining invites? (y/N): ").strip().lower()

                    # Changed this part: Make stop the default action, only continue if user explicitly says "y" or "yes"
                    if user_decision in ["yes", "y"]:
                        logger.info("Continuing automation until all invites are used.")
                        # Click the "Got it" button to dismiss the warning
                        got_it_button = self.driver.find_element(
                            By.XPATH,
                            "//button[.//span[text()='Got it']] | " +
                            "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]"
                        )
                        self.driver.execute_script("arguments[0].click();", got_it_button)
                        time.sleep(1)
                        return True
                    else:
                        logger.info("Stopping automation to save some invites for manual use.")
                        return False

            return True  # No warning found, continue
        except Exception as e:
            logger.error(f"Error checking invitation limit: {str(e)}")
            return True  # Continue if there was an error checking

    def _drain_performance_logs(self):
        """Return newly buffered performance-log messages as parsed dicts.

        Chrome's performance log delivers each network event as a JSON string in
        entry['message']; we unwrap the nested {'message': {...}} envelope.
        get_log() also CLEARS the buffer, so each call returns only events since
        the previous call. Returns [] when performance logging is unavailable.
        """
        if not getattr(self, "perf_logging", False):
            return []
        try:
            raw = self.driver.get_log("performance")
        except Exception as e:
            logger.debug(f"Could not read performance log: {type(e).__name__}: {e}")
            return []

        messages = []
        for entry in raw:
            try:
                messages.append(json.loads(entry["message"])["message"])
            except Exception:
                continue
        return messages

    def _log_quota_from_invite_response(self, request_id, headers):
        """Log any genuine rate-limit headers from a successful invite response.

        As of 2026-06 LinkedIn's verifyQuotaAndCreate endpoint does NOT expose
        remaining quota in its response — the body only contains the invitationUrn
        and the headers are server-routing metadata (x-li-fabric, x-li-pop, etc.).
        We keep this method so future changes to the API are caught automatically.
        """
        quota_headers = {k: v for k, v in headers.items()
                         if any(kw in k.lower() for kw in
                                ("ratelimit", "x-rate-limit", "quota", "remaining"))}
        if quota_headers:
            logger.info(f"[QUOTA] Invite endpoint quota headers found: {quota_headers}")

    def detect_rate_limit_429(self, wait=3.0):
        """Watch the browser's network traffic for an HTTP 429 on the invite call.

        LinkedIn's voyagerRelationshipsDashMemberRelationships endpoint answers
        429 (Too Many Requests) once your invitation quota is spent - even when
        no "limit reached" dialog appears. Because the response arrives a moment
        after the Send click, we poll the performance log for up to `wait`
        seconds. Returns True (and logs an error) if such a 429 is seen.
        On successful responses we also peek at headers/body for quota info.
        """
        if not getattr(self, "perf_logging", False):
            return False

        end = time.time() + wait
        while True:
            for msg in self._drain_performance_logs():
                if msg.get("method") != "Network.responseReceived":
                    continue
                params = msg.get("params", {})
                response = params.get("response", {})
                url = response.get("url", "")
                if not any(frag in url for frag in INVITE_ENDPOINT_FRAGMENTS):
                    continue
                status = response.get("status")
                if status == 429:
                    logger.error(
                        "HTTP 429 (Too Many Requests) from LinkedIn's invitation "
                        f"endpoint:\n    {url}\n"
                        "Your invite quota is exhausted - stopping automation so "
                        "you don't keep hammering the rate limit.")
                    return True
                if status in (200, 201):
                    self._log_quota_from_invite_response(
                        params.get("requestId"), response.get("headers", {}))
            if time.time() >= end:
                return False
            time.sleep(0.5)

    def verify_successful_invitation_sent(self, target_label=None, full_name=None):
        """Confirm the invite actually registered by checking the person's state.

        A real send turns the person's "Invite <Name> to connect" control into a
        "Pending ..." control. We check that this person's Connect control is gone
        and, when possible, that a matching "Pending" control appeared. This is
        more honest than assuming success just because the modal closed (an
        untrusted click closes the modal without sending).
        """
        try:
            # Give the search row a moment to reflect the new state
            time.sleep(2)

            # A limit dialog means the send was blocked
            if not self.check_invitation_limit_warning():
                return False

            if not target_label:
                return True  # nothing to check against; don't block the run

            # Positive signal: a "Pending" control mentioning this person
            if full_name:
                pending = self.driver.find_elements(
                    By.XPATH, "//a[contains(@aria-label, 'Pending')] | "
                              "//button[contains(@aria-label, 'Pending')]")
                for el in pending:
                    label = el.get_attribute("aria-label") or ""
                    if full_name in label:
                        logger.debug(f"Confirmed Pending state for {full_name}")
                        return True

            # Negative signal: this person's Connect control is still present,
            # i.e. the invite did NOT register.
            still_connect = self.driver.find_elements(
                By.XPATH, "//a[@aria-label=" + self._xpath_literal(target_label) + "]")
            if still_connect:
                logger.warning(f"Connect control still present for {target_label} - "
                               f"invite did NOT register (likely an ignored click)")
                return False

            # Connect control gone and no contradicting signal: treat as sent
            logger.debug(f"Connect control for {target_label} is gone - assuming sent")
            return True

        except Exception as e:
            logger.debug(f"Error verifying invitation: {str(e)}")
            return True  # don't hard-stop on a verification hiccup

    @staticmethod
    def _xpath_literal(value):
        """Build a safe XPath string literal (handles embedded quotes)."""
        if '"' not in value:
            return f'"{value}"'
        if "'" not in value:
            return f"'{value}'"
        parts = value.split('"')
        return "concat(" + ", '\"', ".join(f'"{p}"' for p in parts) + ")"

    def display_first_name(self, full_name):
        """Return the name to use in the {name} placeholder.

        Usually just the first token, but keeps compound first names ("João
        Victor", "Ana Júlia", "Maria de Lourdes"): the extra token is included
        only when it is itself a known given name, so surnames (Silva, Santos)
        are dropped.
        """
        if not full_name:
            return ""
        tokens = full_name.split()
        if not tokens:
            return ""
        first = tokens[0]
        if len(tokens) == 1:
            return first

        # "Maria de Lourdes" -> keep connector + following given name
        if _normalize_name_token(tokens[1]) in NAME_CONNECTORS and len(tokens) >= 3:
            if _normalize_name_token(tokens[2]) in COMPOUND_GIVEN_NAMES:
                return f"{first} {tokens[1]} {tokens[2]}"
            return first

        # "João Victor" -> keep second token only if it's a given name
        if _normalize_name_token(tokens[1]) in COMPOUND_GIVEN_NAMES:
            return f"{first} {tokens[1]}"

        return first

    def extract_name_from_aria_label(self, aria_label):
        """Extract the first name from a Connect control's aria-label.

        In the current LinkedIn search UI the Connect control is an anchor whose
        aria-label reads 'Invite <Full Name> to connect'. This is the most
        reliable name source available before opening the modal.
        """
        if not aria_label:
            return None
        match = re.match(r"Invite\s+(.+?)\s+to connect", aria_label, re.IGNORECASE)
        if match:
            full_name = match.group(1).strip()
            if full_name:
                return self.display_first_name(full_name)
        return None

    def extract_name_from_profile(self, connect_button):
        """Extract name using the specific link structure provided."""
        try:
            # First, find the parent container that contains both the button and the name link
            # We'll try going up several levels to find a common container
            parent_element = connect_button
            max_levels = 10  # Try up to 10 parent levels

            for _ in range(max_levels):
                parent_element = parent_element.find_element(By.XPATH, "..")

                # Now look for the specific link pattern within this parent container
                links = parent_element.find_elements(
                    By.XPATH,
                    ".//a[contains(@href, 'linkedin.com/in/')]"
                )

                if links:
                    for link in links:
                        # Look for the span with aria-hidden="true" inside the link
                        try:
                            name_span = link.find_element(By.XPATH, ".//span[@aria-hidden='true']")
                            full_name = name_span.text.strip()

                            if full_name:
                                # Get the first name (before any space)
                                first_name = full_name.split()[0]
                                logger.debug(f"Found name: {full_name}, using first name: {first_name}")
                                return first_name
                        except:
                            continue

                # Try another approach - look for any span that might contain the name
                try:
                    spans = parent_element.find_elements(
                        By.XPATH,
                        ".//span[contains(@class, 'entity-result__title-text')]//span[@aria-hidden='true']"
                    )

                    if spans:
                        for span in spans:
                            name_text = span.text.strip()
                            if name_text and " " in name_text:
                                first_name = name_text.split()[0]
                                logger.debug(f"Found name in title span: {name_text}, using: {first_name}")
                                return first_name
                except:
                    pass

            # If we get here, we couldn't find the name in this specific structure
            # Let's try a more general approach
            all_name_links = self.driver.find_elements(
                By.XPATH,
                "//a[contains(@href, 'linkedin.com/in/')]//span[@aria-hidden='true']"
            )

            # Find the closest one to our button
            if all_name_links:
                button_location = connect_button.location
                closest_distance = float('inf')
                closest_name = None

                for elem in all_name_links:
                    try:
                        elem_location = elem.location
                        distance = ((elem_location['x'] - button_location['x'])**2 +
                                    (elem_location['y'] - button_location['y'])**2)**0.5

                        if distance < closest_distance:
                            name_text = elem.text.strip()
                            if name_text:
                                closest_distance = distance
                                closest_name = name_text.split()[0]
                    except:
                        continue

                if closest_name:
                    logger.debug(f"Found name using proximity: {closest_name}")
                    return closest_name

            logger.debug("Could not extract name from profile")
            return None

        except Exception as e:
            logger.debug(f"Error extracting name: {str(e)}")
            return None

    def extract_name_from_modal(self, shadow_root=None):
        """Extract name from the modal after clicking connect.

        The first invite modal body reads "Personalize your invitation to
        <strong>Full Name</strong> by adding a note." Since the modal lives in the
        #interop-outlet shadow root, search there (CSS only) when available.
        """
        try:
            if shadow_root is not None:
                try:
                    for el in shadow_root.find_elements(
                            By.CSS_SELECTOR, ".artdeco-modal__content strong"):
                        text = el.text.strip()
                        if text:
                            first_name = self.display_first_name(text)
                            logger.debug(f"Extracted name from modal body: {first_name}")
                            return first_name
                except Exception:
                    pass

            # Legacy light-DOM fallback (kept for resilience)
            strong_elements = self.driver.find_elements(
                By.XPATH,
                "//div[@data-test-modal]//div[contains(@class, 'artdeco-modal__content')]//strong | "
                "//div[contains(@class, 'artdeco-modal')]//div[contains(@class, 'artdeco-modal__content')]//strong")
            for el in strong_elements:
                text = el.text.strip()
                if text:
                    first_name = self.display_first_name(text)
                    logger.debug(f"Extracted name from modal body: {first_name}")
                    return first_name

            # Look for the specific name structure in the modal
            modal_name_elements = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'artdeco-modal')]//span[@aria-hidden='true']"
            )

            for elem in modal_name_elements:
                name_text = elem.text.strip()
                if name_text and len(name_text.split()) >= 1:
                    # Skip text that's likely not a name
                    if name_text.lower() in ["connect", "add a note", "send", "include", "add", "invite"]:
                        continue

                    first_name = name_text.split()[0]
                    logger.debug(f"Extracted name from modal: {first_name}")
                    return first_name

            # Try alternative selectors if the above didn't work
            selectors = [
                "//div[contains(@class, 'artdeco-modal')]//h2",
                "//div[contains(@class, 'artdeco-modal')]//h3",
                "//div[contains(@class, 'send-invite')]//h2"
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text:
                            # Common patterns in the modal title
                            if "Connect with " in text:
                                name = text.replace("Connect with ", "")
                                first_name = name.split()[0]
                                logger.debug(f"Extracted name from modal title: {first_name}")
                                return first_name
                            elif "Invite " in text and " to connect" in text:
                                name = text.replace("Invite ", "").replace(" to connect", "")
                                first_name = name.split()[0]
                                logger.info(f"Extracted name from invitation text: {first_name}")
                                return first_name
                except:
                    continue

            logger.debug("Could not extract name from modal")
            return None
        except Exception as e:
            logger.debug(f"Error extracting name from modal: {str(e)}")
            return None

    def process_page(self):
        """Process all valid Connect controls on the current page.

        In the current LinkedIn search UI the Connect control is an <a> anchor
        (aria-label="Invite <Name> to connect"), not a <button>. Already-invited
        profiles show "Pending" and existing connections show "Message", both of
        which are naturally excluded by the selector below.
        """
        # Wait for the new search results UI to load
        try:
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//section[@aria-label='Primary content'] | //div[@role='listitem']")))
        except:
            logger.warning("Could not find search results, trying to continue anyway")

        # Nudge the lazy-loaded result list so every profile renders before we start
        try:
            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
                time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        except:
            pass

        # Connect controls are anchors exposing aria-label="Invite <Name> to connect"
        connect_xpath = ("//a[starts-with(@aria-label, 'Invite ') and "
                         "contains(@aria-label, 'to connect')]")

        # Track profiles we've already attempted by their aria-label. A successful
        # invite turns the anchor into "Pending", so it leaves the selector anyway,
        # but this also guards against re-finding an unchanged element.
        processed_labels = set()

        while True:
            # Check for invitation limit warning before processing each profile
            if not self.check_invitation_limit_warning():
                logger.info("Stopping automation due to invitation limit or user choice.")
                return False  # Signal to stop the automation

            # Re-find anchors each iteration to avoid stale references
            connect_links = self.driver.find_elements(By.XPATH, connect_xpath)

            target = None
            target_label = None
            for link in connect_links:
                try:
                    label = link.get_attribute("aria-label")
                except Exception:
                    continue
                if label and label not in processed_labels:
                    target = link
                    target_label = label
                    break

            if target is None:
                logger.info("No more Connect controls to process on this page")
                break

            processed_labels.add(target_label)

            # Most reliable name source: the Connect anchor's own aria-label
            name = self.extract_name_from_aria_label(target_label)
            if name:
                logger.info(f"Processing {target_label} -> using first name: {name}")

            try:
                # Scroll to the Connect control
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(random.uniform(1, 2))  # Random delay to appear more human-like

                # Click the Connect control with a REAL (trusted) click. LinkedIn's
                # handler that opens the invite modal ignores synthetic JS clicks
                # (event.isTrusted == false), so a native Selenium click is required;
                # _robust_click falls back to JS only if the native click is blocked.
                self._robust_click(target, f"Connect control ({target_label})")
                time.sleep(3)  # Give the modal a moment to fully open before interacting

                # The invite modal renders inside the #interop-outlet Shadow DOM.
                # Selenium can't reach it with XPath/By.ID, so grab the shadow root
                # and drive the modal through it with CSS selectors.
                shadow = self.get_modal_shadow_root(timeout=10)
                if shadow is None:
                    if not self.check_invitation_limit_warning():
                        return False
                    logger.warning(f"No modal appeared when clicking Connect for {target_label}. Skipping.")
                    self.connections_skipped += 1
                    continue

                # Check again for limit reached after clicking connect
                if not self.check_invitation_limit_warning():
                    logger.info("Stopping automation due to invitation limit.")
                    return False

                # Some members require their email to be invited. We can't supply
                # it, so cancel this attempt and move on to the next profile.
                if self.modal_requires_email(shadow):
                    logger.warning(f"{target_label} requires an email to connect. Cancelling and skipping.")
                    self.dismiss_open_modal()
                    self.wait_modal_closed(shadow, timeout=3)
                    self.connections_skipped += 1
                    time.sleep(random.uniform(1, 2))
                    continue

                # If name wasn't found from the aria-label, try to extract it from the modal
                if not name:
                    name = self.extract_name_from_modal(shadow)

                # If no_message flag is enabled, click "Send without a note" button
                if self.no_message:
                    send_without_note_btn = self.find_in_shadow(
                        shadow, "button[aria-label='Send without a note']", require_enabled=True)
                    if send_without_note_btn is None:
                        if not self.check_invitation_limit_warning():
                            return False
                        logger.warning(f"No 'Send without a note' button found for {target_label}. Skipping.")
                        self.connections_skipped += 1
                        continue
                    self._robust_click(send_without_note_btn, "Send without a note button")
                    logger.info(f"Sending invitation without a note to {name or target_label}")
                else:
                    # Otherwise, follow the original flow with a note
                    add_note_btn = self.find_in_shadow(
                        shadow, "button[aria-label='Add a note']", require_enabled=True)
                    if add_note_btn is None:
                        if not self.check_invitation_limit_warning():
                            return False
                        logger.warning(f"No 'Add a note' button found for {target_label}. Skipping.")
                        self.connections_skipped += 1
                        continue
                    self._robust_click(add_note_btn, "Add a note button")

                    # Wait for the note text area (still inside the same shadow root)
                    message_box = self.find_in_shadow(shadow, "#custom-message")
                    if message_box is None:
                        if not self.check_invitation_limit_warning():
                            return False
                        logger.warning(f"No message box appeared for {target_label}. Skipping.")
                        self.connections_skipped += 1
                        continue

                    # Prepare personalized message
                    personalized_message = self.personalize_message(name)

                    # Debug output to verify message preparation
                    logger.info(f"Sending message to {name or target_label}: {personalized_message.splitlines()[0] if personalized_message else ''}")

                    # Type the note so LinkedIn registers it and enables Send
                    self.fill_message_box(message_box, personalized_message)

                    # Wait a moment for the Send button to be enabled
                    time.sleep(1)

                    # DEBUG: report what LinkedIn actually has in the textarea
                    try:
                        textarea_len = self.driver.execute_script(
                            "return (arguments[0].value || '').length;", message_box)
                        logger.debug(f"Textarea length as seen by LinkedIn: {textarea_len} "
                                     f"(expected {self._message_length(personalized_message)})")
                    except Exception:
                        pass

                    # Find the Send button (enabled only once the note registers)
                    send_btn = self.find_in_shadow(
                        shadow, "button[aria-label='Send invitation']", require_enabled=True)
                    if send_btn is None:
                        if not self.check_invitation_limit_warning():
                            return False
                        logger.warning(f"Send button never became clickable for {target_label} "
                              f"(note may not have registered). Skipping.")
                        self.connections_skipped += 1
                        continue

                    # Scroll the Send button into view and click it (trusted click)
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", send_btn)
                    except Exception:
                        pass
                    logger.debug(f"Clicking Send (enabled={send_btn.is_enabled()}) for {target_label}")
                    self._robust_click(send_btn, "Send invitation button")

                # Wait for the modal to close (it leaves the shadow root when sent)
                if not self.wait_modal_closed(shadow, timeout=5):
                    if not self.check_invitation_limit_warning():
                        return False
                    logger.warning(f"Modal never closed for {target_label}. Skipping.")
                    continue

                # Network-level rate-limit guard: if the Send POST came back 429,
                # we're out of quota - stop now even if the UI showed no dialog.
                if self.detect_rate_limit_429():
                    return False

                # Verify the invitation actually registered (person turned Pending)
                m = re.match(r"Invite\s+(.+?)\s+to connect", target_label)
                full_name = m.group(1) if m else None
                if self.verify_successful_invitation_sent(target_label, full_name):
                    self.connections_sent += 1
                    logger.info(
                        f"Invitation sent to {name or target_label} "
                        f"[sent={self.connections_sent}, failed={self.connections_failed}, "
                        f"skipped={self.connections_skipped}]")
                else:
                    # A limit dialog means we must stop; otherwise the invite simply
                    # didn't register for this person - log it and move on.
                    if not self.check_invitation_limit_warning():
                        return False
                    self.connections_failed += 1
                    logger.warning(
                        f"Invite to {target_label} did not register; moving to next person "
                        f"[sent={self.connections_sent}, failed={self.connections_failed}, "
                        f"skipped={self.connections_skipped}]")

                # Random delay between invitations to appear more human-like
                time.sleep(random.uniform(3, 5))

            except ElementClickInterceptedException:
                logger.warning(f"Connect control for {target_label} was intercepted by another element")
                # Check if it's the invitation limit warning
                if not self.check_invitation_limit_warning():
                    return False

                # Try to close any other modal that might be open
                self.dismiss_open_modal()

            except Exception as e:
                logger.error(f"Error processing {target_label}: {str(e)}")
                # Check if it's the invitation limit warning
                if not self.check_invitation_limit_warning():
                    return False

                # Try to close any modal that might be open
                try:
                    self.dismiss_open_modal()
                except:
                    pass

        return True  # Continue automation

    def select_search_tab(self):
        """Switch the driver to the tab that shows LinkedIn people-search results.

        When attaching to an already-open browser, Selenium may be pointed at a
        different tab than the one with the search results, which makes every
        find_element come back empty. We scan all open tabs and switch to the
        people-search results tab so the rest of the run drives the right window.
        Returns True if a suitable tab was selected.
        """
        try:
            handles = self.driver.window_handles
        except Exception as e:
            logger.error(f"Could not enumerate browser tabs: {e}")
            return False

        people_search = None
        any_search = None
        for h in handles:
            try:
                self.driver.switch_to.window(h)
                url = (self.driver.current_url or "").lower()
            except Exception:
                continue
            if "linkedin.com/search/results/people" in url:
                people_search = h
                break
            if any_search is None and "linkedin.com/search/results" in url:
                any_search = h

        chosen = people_search or any_search
        if chosen is not None:
            self.driver.switch_to.window(chosen)
            logger.info(f"Using tab: {self.driver.current_url}")
            return True

        logger.warning("no LinkedIn people-search tab found among the open tabs. "
              "Make sure the search results page is open. Using the current tab.")
        # Leave the driver focused on whatever the last tab was; fall back to first
        if handles:
            self.driver.switch_to.window(handles[0])
        return False

    def go_to_next_page(self):
        """Go to the next or previous page of search results depending on reverse setting. Returns False if no navigation is possible."""
        try:
            # Check for invitation limit warning before navigating
            if not self.check_invitation_limit_warning():
                return False

            # The new pagination control uses stable data-testid attributes. The
            # active button ends in "-visible"; an unavailable one ends in
            # "-hidden" (or is disabled).
            direction = "prev" if self.reverse else "next"
            nav_xpath = f"//button[starts-with(@data-testid, 'pagination-controls-{direction}-button')]"
            nav_css = f"button[data-testid^='pagination-controls-{direction}-button']"

            # Find the button (it may exist but be hidden/disabled)
            nav_button = None
            try:
                nav_button = self.short_wait.until(EC.presence_of_element_located((By.XPATH, nav_xpath)))
            except (TimeoutException, NoSuchElementException):
                nav_button = None

            # Fallback: the pagination control may render inside the interop shadow DOM
            if nav_button is None:
                for host in self.driver.find_elements(
                        By.CSS_SELECTOR, "#interop-outlet, [data-testid='interop-shadowdom']"):
                    try:
                        sr = host.shadow_root
                    except Exception:
                        continue
                    found = sr.find_elements(By.CSS_SELECTOR, nav_css)
                    if found:
                        nav_button = found[0]
                        break

            if nav_button is None:
                logger.info(f"No {'previous' if self.reverse else 'next'} page button found")
                return False

            testid = nav_button.get_attribute("data-testid") or ""
            if "hidden" in testid or nav_button.get_attribute("disabled"):
                logger.info(f"No more pages available ({'previous' if self.reverse else 'next'} button is disabled)")
                return False

            # Boundary checks based on the currently highlighted page indicator
            if self.reverse:
                try:
                    current_page_elem = self.driver.find_element(By.XPATH, "//button[@aria-current='true']")
                    if current_page_elem.text.strip() == "1":
                        logger.info("Reached first page (page 1)")
                        return False
                except:
                    # If we can't find the current page element, just continue
                    pass
            # If going forward, check if we've reached page 100 (LinkedIn limit)
            else:
                try:
                    current_page_elem = self.driver.find_element(By.XPATH, "//button[@aria-current='true']")
                    if current_page_elem.text.strip() == "100":
                        logger.info("Reached LinkedIn's page limit (page 100)")
                        return False
                except:
                    # If we can't find the current page element, just continue
                    pass

            # Scroll to the button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", nav_button)
            time.sleep(1)

            # Store the current URL to check if we actually navigate
            current_url = self.driver.current_url

            # Click the button with a real (trusted) click, JS as fallback
            self._robust_click(nav_button)

            # Wait for the page to load
            time.sleep(5)

            # Check if URL changed or if page content updated
            if self.driver.current_url != current_url:
                return True

            # Additional check: try to find a loading indicator or wait for it to disappear
            try:
                loading_element = self.driver.find_element(By.XPATH, "//div[contains(@class, 'loading')]")
                self.wait.until(EC.staleness_of(loading_element))
            except:
                # If no loading indicator found, just continue
                pass

            return True

        except (TimeoutException, NoSuchElementException):
            direction = "previous" if self.reverse else "next"
            logger.warning(f"No {direction} page button found or it's disabled")
            return False
        except Exception as e:
            logger.error(f"Error navigating to {'previous' if self.reverse else 'next'} page: {str(e)}")
            return False

    def run_automation(self, max_pages=100):
        """Run the full automation process."""
        page_num = 1

        # Keep the PC awake for the entire run
        self._prevent_sleep()

        # Make sure we're driving the tab that actually has the search results
        # (Selenium may attach to a different tab of an existing browser).
        self.select_search_tab()

        try:
            while page_num <= max_pages:
                logger.info(f"--- Processing page {page_num} ---")

                # Check for invitation limit warning before starting the page
                if not self.check_invitation_limit_warning():
                    logger.info("Stopping automation due to invitation limit detection.")
                    break

                # Process Connect buttons only. People who can only be followed (no
                # Connect button) are intentionally skipped - we only want real
                # connection requests.
                if not self.process_page():
                    logger.info("Automation stopped due to invitation limit or user choice.")
                    break

                # Try to go to next/previous page based on reverse setting
                if not self.go_to_next_page():
                    direction = "first" if self.reverse else "last"
                    logger.info(f"Reached the {direction} page or encountered an error")
                    break

                page_num += 1

                # Random delay between pages
                time.sleep(random.uniform(3, 5))
        finally:
            self._allow_sleep()

        direction = "reverse" if self.reverse else "forward"
        logger.info(f"Completed automation in {direction} direction! Processed {page_num} pages.")
        logger.info(
            f"Session summary — sent: {self.connections_sent} | "
            f"failed to register: {self.connections_failed} | "
            f"skipped (email/modal issues): {self.connections_skipped}")

    def _prevent_sleep(self):
        """Tell Windows not to sleep or turn off the display while the bot runs."""
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
            logger.info("Sleep prevention enabled — PC will stay awake during automation.")
        except Exception as e:
            logger.warning(f"Could not enable sleep prevention: {e}")

    def _allow_sleep(self):
        """Restore normal Windows sleep behaviour after the bot finishes."""
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
            logger.debug("Sleep prevention disabled — normal power settings restored.")
        except Exception as e:
            logger.debug(f"Could not restore sleep settings: {e}")

    def close(self):
        """Close the browser."""
        self.driver.quit()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='LinkedIn Tech Recruiters Auto Connect')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Automatically continue past "close to limit" warnings (will still stop at hard limit)')
    parser.add_argument('-m', '--message', default='message.txt',
                        help='Path to message template file (default: message.txt)')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='Navigate in reverse (use Previous button instead of Next)')
    parser.add_argument('-n', '--no-message', action='store_true',
                        help='Send invitations without a note')
    parser.add_argument('-l', '--log-level', default='DEBUG',
                        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'],
                        help='Console/file log verbosity (default: DEBUG)')
    return parser.parse_args()


# Example usage
if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Map the friendly "WARN" choice to logging.WARNING
    level_name = "WARNING" if args.log_level == "WARN" else args.log_level
    setup_logging(level=getattr(logging, level_name, logging.DEBUG))

    # Log the active run configuration up front
    logger.info("=" * 60)
    logger.info("LinkedIn People Connect Bot - starting up")
    logger.info("Active configuration:")
    logger.info(f"  Mode            : {'send WITHOUT note (-n)' if args.no_message else 'send WITH personalized note'}")
    if not args.no_message:
        logger.info(f"  Message file    : {args.message}")
    logger.info(f"  Navigation      : {'REVERSE (Previous)' if args.reverse else 'forward (Next)'}")
    logger.info(f"  Auto-continue   : {'on (-y) - skip close-to-limit prompts' if args.yes else 'off - will prompt near limit'}")
    logger.info(f"  Browser         : attach to existing (127.0.0.1:9222)")
    logger.info(f"  Log level       : {args.log_level}")
    logger.info(f"  Log file        : {LOG_FILE} (overwritten each run)")
    logger.info("=" * 60)

    # To use with an already opened browser, set use_existing_browser=True
    # Pass the auto_continue flag from command line arguments
    automator = LinkedInAutomator(use_existing_browser=True, auto_continue=args.yes,
                                  message_file=args.message, reverse=args.reverse,
                                  no_message=args.no_message)

    try:
        # Run the automation
        automator.run_automation(max_pages=100)
    except KeyboardInterrupt:
        logger.warning("Automation stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Automation stopped due to error: {str(e)}")
    finally:
        # Don't close the browser if we're using an existing one
        if not automator.use_existing_browser:
            automator.close()