from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import random
import argparse
import sys
import os

class LinkedInPeopleConnectionBot:
    def __init__(self, use_existing_browser=False, auto_continue=False, message_file="message.txt"):
        """Initialize the LinkedIn People Connection Bot."""
        # Store the browser mode setting
        self.use_existing_browser = use_existing_browser
        # Store whether to auto-continue past warnings
        self.auto_continue = auto_continue

        if not use_existing_browser:
            # Set up a new browser instance
            self.driver = webdriver.Chrome()  # You can change to Firefox or other browsers
        else:
            # For working with an already opened browser tab
            from selenium.webdriver.chrome.options import Options
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=chrome_options)

        # Wait configuration
        self.wait = WebDriverWait(self.driver, 10)
        self.short_wait = WebDriverWait(self.driver, 3)

        # Load message template from file
        self.message_template = self.load_message_template(message_file)

    def load_message_template(self, file_path):
        """Load message template from a text file."""
        try:
            if not os.path.exists(file_path):
                print(f"Warning: Message template file '{file_path}' not found. Using default message.")
                return "Hello {name}! I'd like to connect with you."

            with open(file_path, 'r', encoding='utf-8') as file:
                template = file.read().strip()

            # Truncate to 300 characters if necessary (LinkedIn's limit)
            if len(template) > 300:
                template = template[:300]
                print(f"Warning: Message template truncated to 300 characters.")

            return template

        except Exception as e:
            print(f"Error loading message template: {str(e)}. Using default message.")
            return "Hello {name}! I'd like to connect with you."

    def personalize_message(self, name=None):
        """Personalize the message template with the given name."""
        if name:
            return self.message_template.replace("{name}", name)
        else:
            # If no name found, replace {name} with empty string
            return self.message_template.replace("{name}", "")

    # Add these methods to the LinkedInPeopleConnectionBot class (after personalize_message method)

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
                                print(f"Found name: {full_name}, using first name: {first_name}")
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
                                print(f"Found name in title span: {name_text}, using: {first_name}")
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
                    print(f"Found name using proximity: {closest_name}")
                    return closest_name

            print("Could not extract name from profile")
            return None

        except Exception as e:
            print(f"Error extracting name: {str(e)}")
            return None

    def extract_name_from_modal(self):
        """Extract name from the modal after clicking connect."""
        try:
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
                    print(f"Extracted name from modal: {first_name}")
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
                                print(f"Extracted name from modal title: {first_name}")
                                return first_name
                            elif "Invite " in text and " to connect" in text:
                                name = text.replace("Invite ", "").replace(" to connect", "")
                                first_name = name.split()[0]
                                print(f"Extracted name from invitation text: {first_name}")
                                return first_name
                except:
                    continue

            print("Could not extract name from modal")
            return None
        except Exception as e:
            print(f"Error extracting name from modal: {str(e)}")
            return None

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
                print("\n" + "="*50)
                print("CRITICAL: You've reached the weekly invitation limit! Stopping automation.")
                print("="*50)

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
                print("\n" + "="*50)
                print("WARNING: You're close to the weekly invitation limit!")
                print("="*50)

                if self.auto_continue:
                    print("Auto-continue enabled (-y flag). Automatically continuing past the warning.")
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
                        print("Continuing automation until all invites are used.")
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
                        print("Stopping automation to save some invites for manual use.")
                        return False

            return True  # No warning found, continue
        except Exception as e:
            print(f"Error checking invitation limit: {str(e)}")
            return True  # Continue if there was an error checking

    # Add this method to the LinkedInPeopleConnectionBot class (after check_invitation_limit_warning method)

    def verify_successful_invitation_sent(self, connect_button):
        """Verify that the invitation was actually sent successfully."""
        try:
            # Check if any limit warning dialog appeared
            if not self.check_invitation_limit_warning():
                return False

            # Check if the connect button changed to "Pending" or disappeared
            try:
                # Refresh the button's state
                # Get current button text if it still exists
                try:
                    button_text = connect_button.text.strip()
                    if button_text == "Pending":
                        return True  # Successfully sent
                    elif button_text == "Connect":
                        print("WARNING: Button still shows 'Connect' - invitation may not have been sent")
                        return False  # Not sent
                except:
                    # Button might be stale, look for a Pending button in its place
                    parent_element = connect_button.find_element(By.XPATH, "..")
                    pending_buttons = parent_element.find_elements(By.XPATH, ".//button[contains(text(), 'Pending')]")
                    if pending_buttons:
                        return True  # Successfully sent
            except:
                # Button is completely gone or stale, try looking for a success message
                success_elements = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(text(), 'Invitation sent')] | " +
                    "//span[contains(text(), 'Invitation sent')]"
                )
                if success_elements:
                    return True  # Successfully sent

            # Look for any error messages that indicate failure
            error_elements = self.driver.find_elements(
                By.XPATH,
                "//div[contains(text(), 'unable to send')] | " +
                "//div[contains(text(), 'invitation limit')] | " +
                "//div[contains(text(), 'cannot send')] | " +
                "//div[contains(@class, 'error')]"
            )
            if error_elements:
                print("ERROR: Found error message indicating invitation was not sent")
                return False  # Not sent

            # If we can't definitively determine success or failure, assume failure to be safe
            print("WARNING: Could not verify if invitation was sent. Assuming it failed.")
            return False
        except Exception as e:
            print(f"Error verifying invitation: {str(e)}")
            return False  # Assume failure on error

    # Add this method to the LinkedInPeopleConnectionBot class (after verify_successful_invitation_sent method)

    def process_page(self):
        """Process all valid connect buttons on the current page."""
        # Wait for the search results container to load
        try:
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "search-results-container")))
        except:
            print("Could not find search-results-container, trying to continue anyway")

        # Find all buttons on the page
        buttons = self.driver.find_elements(By.TAG_NAME, "button")

        connect_buttons = []

        # Filter for Connect buttons only
        for button in buttons:
            try:
                button_text = button.text.strip()
                if button_text == "Connect":
                    connect_buttons.append(button)
            except:
                continue

        print(f"Found {len(connect_buttons)} Connect buttons on this page")

        # Process each Connect button
        for i, button in enumerate(connect_buttons):
            try:
                # Check for invitation limit warning before processing each button
                if not self.check_invitation_limit_warning():
                    print("Stopping automation due to invitation limit or user choice.")
                    return False  # Signal to stop the automation

                # Scroll to the button
                self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                time.sleep(random.uniform(1, 2))  # Random delay to appear more human-like

                # Check if it's still a Connect button (might have changed during iteration)
                if button.text.strip() != "Connect":
                    continue

                # Try to extract name before clicking
                name = self.extract_name_from_profile(button)

                # Click the Connect button using JavaScript to avoid intercepted clicks
                self.driver.execute_script("arguments[0].click();", button)

                # Wait for the modal to appear
                try:
                    self.wait.until(EC.presence_of_element_located((By.ID, "send-invite-modal")))
                except:
                    # If the standard ID doesn't work, try a more generic approach
                    try:
                        self.wait.until(EC.presence_of_element_located(
                            (By.XPATH, "//div[contains(@class, 'artdeco-modal')]")))
                    except:
                        # If no modal appears, check if we hit the limit
                        if not self.check_invitation_limit_warning():
                            return False
                        print(f"No modal appeared when clicking Connect button {i+1}. Skipping.")
                        continue

                # Check again for limit reached after clicking connect
                if not self.check_invitation_limit_warning():
                    print("Stopping automation due to invitation limit.")
                    return False

                # If name wasn't found before, try to extract it from the modal
                if not name:
                    name = self.extract_name_from_modal()

                # Find and click "Add a note" button - using JavaScript click
                try:
                    add_note_btn = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[.//span[text()='Add a note']]")))
                    self.driver.execute_script("arguments[0].click();", add_note_btn)
                except:
                    # If "Add a note" button doesn't appear, check for limit warning
                    if not self.check_invitation_limit_warning():
                        return False
                    print(f"No 'Add a note' button found for button {i+1}. Skipping.")
                    continue

                # Wait for the text area to be visible
                try:
                    message_box = self.wait.until(EC.element_to_be_clickable((By.ID, "custom-message")))
                except:
                    # If no message box appears, check if we hit the limit
                    if not self.check_invitation_limit_warning():
                        return False
                    print(f"No message box appeared for button {i+1}. Skipping.")
                    continue

                # Prepare personalized message
                personalized_message = self.personalize_message(name)

                # Debug output to verify message preparation
                print(f"Sending message to candidate {i+1}: {personalized_message[:50]}{'...' if len(personalized_message) > 50 else ''}")

                # Clear and fill the message box - using JS to avoid character issues
                message_box.clear()

                # Use JavaScript to set the value to avoid BMP character issues
                self.driver.execute_script(
                    "arguments[0].value = arguments[1];",
                    message_box,
                    personalized_message
                )

                # Trigger an input event to ensure LinkedIn recognizes the text entry
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    message_box
                )

                # Wait a moment for the Send button to be enabled
                time.sleep(2)

                # Find the Send button
                try:
                    send_btn = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[.//span[text()='Send']]")))
                except:
                    # If Send button doesn't become clickable, check for limit warning
                    if not self.check_invitation_limit_warning():
                        return False
                    print(f"Send button never became clickable for button {i+1}. Skipping.")
                    continue

                # Click the Send button using JavaScript
                self.driver.execute_script("arguments[0].click();", send_btn)

                # Wait for the modal to close or for a limit message to appear
                try:
                    self.short_wait.until(EC.invisibility_of_element_located((By.ID, "send-invite-modal")))
                except:
                    # If the standard ID doesn't work, try a more generic approach
                    try:
                        self.short_wait.until(EC.invisibility_of_element_located(
                            (By.XPATH, "//div[contains(@class, 'artdeco-modal')]")))
                    except:
                        # If modal doesn't close, check for limit warning
                        if not self.check_invitation_limit_warning():
                            return False
                        print(f"Modal never closed for button {i+1}. Skipping.")
                        continue

                # Verify the invitation was actually sent successfully
                if self.verify_successful_invitation_sent(button):
                    print(f"Successfully sent invitation {i+1}/{len(connect_buttons)}")
                else:
                    # If verification fails, check for limit warning one more time
                    if not self.check_invitation_limit_warning():
                        return False
                    print(f"Failed to send invitation {i+1}/{len(connect_buttons)} - possibly hit invitation limit")
                    return False  # Stop automation if we can't verify success

                # Random delay between invitations to appear more human-like
                time.sleep(random.uniform(3, 5))

            except ElementClickInterceptedException:
                print(f"Button {i+1} was intercepted by another element")
                # Check if it's the invitation limit warning
                if not self.check_invitation_limit_warning():
                    return False

                # Try to close any other modal that might be open
                try:
                    close_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Dismiss')]")
                    if close_buttons:
                        self.driver.execute_script("arguments[0].click();", close_buttons[0])
                except:
                    pass

            except Exception as e:
                print(f"Error processing button {i+1}: {str(e)}")
                # Check if it's the invitation limit warning
                if not self.check_invitation_limit_warning():
                    return False

                # Try to close any modal that might be open
                try:
                    close_button = self.driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Dismiss')]")
                    self.driver.execute_script("arguments[0].click();", close_button)
                except:
                    pass

        return True  # Continue automation

    # Add these methods to the LinkedInPeopleConnectionBot class (after process_page method)

    def click_follow_buttons(self):
        """Click all Follow buttons on the page."""
        follow_buttons = self.driver.find_elements(By.XPATH, "//button[.//span[text()='Follow']]")

        for i, button in enumerate(follow_buttons):
            try:
                # Check for invitation limit warning before processing
                if not self.check_invitation_limit_warning():
                    return False

                # Scroll to the button
                self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                time.sleep(random.uniform(0.5, 1))

                # Click the Follow button using JavaScript
                self.driver.execute_script("arguments[0].click();", button)
                print(f"Followed profile {i+1}/{len(follow_buttons)}")

                # Short delay
                time.sleep(random.uniform(1, 2))

            except Exception as e:
                print(f"Error following profile {i+1}: {str(e)}")

        return True

    def go_to_next_page(self):
        """Go to the next page of search results. Returns False if no next page."""
        try:
            # Check for invitation limit warning before navigating
            if not self.check_invitation_limit_warning():
                return False

            # Find the Next button
            next_button = self.short_wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(@aria-label, 'Next') and not(contains(@class, 'disabled'))]")))

            # Check if we've reached page 100 (LinkedIn limit)
            try:
                current_page_elem = self.driver.find_element(By.XPATH, "//button[@aria-current='true']")
                if current_page_elem.text == "100":
                    print("Reached LinkedIn's page limit (page 100)")
                    return False
            except:
                # If we can't find the current page element, just continue
                pass

            # Scroll to the Next button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(1)

            # Store the current URL to check if we actually navigate
            current_url = self.driver.current_url

            # Click the Next button using JavaScript
            self.driver.execute_script("arguments[0].click();", next_button)

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
            print("No next page button found or it's disabled")
            return False
        except Exception as e:
            print(f"Error navigating to next page: {str(e)}")
            return False

    # Add this method to the LinkedInPeopleConnectionBot class (after go_to_next_page method)

    def run_automation(self, max_pages=100):
        """Run the full automation process."""
        page_num = 1

        while page_num <= max_pages:
            print(f"\nProcessing page {page_num}")

            # Check for invitation limit warning before starting the page
            if not self.check_invitation_limit_warning():
                print("Stopping automation due to invitation limit detection.")
                break

            # Process Connect buttons
            if not self.process_page():
                print("Automation stopped due to invitation limit or user choice.")
                break

            # Process Follow buttons
            if not self.click_follow_buttons():
                print("Automation stopped due to invitation limit or user choice.")
                break

            # Try to go to next page
            if not self.go_to_next_page():
                print("Reached the last page or encountered an error")
                break

            page_num += 1

            # Random delay between pages
            time.sleep(random.uniform(3, 5))

        print(f"Completed automation! Processed {page_num} pages.")

# Update the main block in the file:
if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # To use with an already opened browser, set use_existing_browser=True
    # Pass the auto_continue flag from command line arguments
    automator = LinkedInPeopleConnectionBot(use_existing_browser=True, auto_continue=args.yes, message_file=args.message)

    try:
        # Run the automation
        automator.run_automation(max_pages=100)
    except KeyboardInterrupt:
        print("\nAutomation stopped by user")
    except Exception as e:
        print(f"\nAutomation stopped due to error: {str(e)}")
    finally:
        # Don't close the browser if we're using an existing one
        if not automator.use_existing_browser:
            automator.close()

    def close(self):
        """Close the browser."""
        self.driver.quit()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='LinkedIn People Connection Bot')
    parser.add_argument('-y', '--yes', action='store_true',
                        help='Automatically continue past "close to limit" warnings (will still stop at hard limit)')
    parser.add_argument('-m', '--message', default='message.txt',
                        help='Path to message template file (default: message.txt)')
    return parser.parse_args()


# Example usage
if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # To use with an already opened browser, set use_existing_browser=True
    # Pass the auto_continue flag from command line arguments
    automator = LinkedInPeopleConnectionBot(use_existing_browser=True, auto_continue=args.yes, message_file=args.message)

    try:
        print("LinkedIn People Connection Bot initialized successfully!")
        print(f"Message template loaded: {automator.message_template[:50]}{'...' if len(automator.message_template) > 50 else ''}")
    except KeyboardInterrupt:
        print("\nAutomation stopped by user")
    except Exception as e:
        print(f"\nAutomation stopped due to error: {str(e)}")
    finally:
        # Don't close the browser if we're using an existing one
        if not automator.use_existing_browser:
            automator.close()