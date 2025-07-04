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