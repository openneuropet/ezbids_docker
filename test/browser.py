import os
import pathlib
import sys
import time
from socket import gethostname

import requests
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL verification for self-signed certificates
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def check_text_on_page(driver, target_text, timeout=40, check_interval=2):
    """
    Check if a specific text appears on the webpage.

    Args:
        driver: Selenium WebDriver instance
        target_text: Text to search for on the page
        timeout: Maximum time to wait for the text (in seconds)
        check_interval: Time between checks (in seconds)

    Returns:
        dict: Dictionary with element details if found, empty dictionary otherwise
            - found: Boolean indicating if the text was found
            - tag: Element tag name (if found)
            - text: Full text content of the element (if found)
            - html: HTML of the element (if found)
            - css_selector: CSS selector for the element (if found)
            - location: Dictionary with x, y coordinates of the element (if found)
            - size: Dictionary with width, height of the element (if found)
    """
    print(f"\n=== Checking for '{target_text}' text on webpage ===\n")
    sys.stdout.flush()

    # Initialize result dictionary
    result = {"found": False}

    # Wait for the page to load and refresh it
    time.sleep(5)  # Initial wait for page load
    driver.refresh()
    time.sleep(5)  # Wait after refresh

    # Set a timeout for checking the text
    end_time = time.time() + timeout

    while time.time() < end_time and not result["found"]:
        # Get all elements on the page
        elements = driver.find_elements(By.XPATH, "//*")

        # Check each element for text content
        for element in elements:
            try:
                text = element.text.strip()
                if text and target_text in text:
                    result["found"] = True

                    # Get element location and size
                    location = element.location
                    size = element.size

                    # Generate CSS selector for the element
                    css_selector = generate_css_selector(driver, element)

                    # Add element details to result dictionary
                    result.update(
                        {
                            "tag": element.tag_name,
                            "text": text,
                            "html": element.get_attribute("outerHTML"),
                            "css_selector": css_selector,
                            "location": location,
                            "size": size,
                        }
                    )

                    print(f"\n✓ PASS: Found '{target_text}' text in element:")
                    print(f"Tag: {element.tag_name}")
                    print(f"Text: '{text}'")
                    print(f"CSS Selector: {css_selector}")
                    print(f"Location: x={location['x']}, y={location['y']}")
                    print(f"Size: width={size['width']}, height={size['height']}")
                    sys.stdout.flush()
                    break
            except:
                continue

        if not result["found"]:
            elapsed = time.time() - (end_time - timeout)
            print(f"Checking for '{target_text}' text... (elapsed: {elapsed:.1f}s)")
            sys.stdout.flush()
            time.sleep(check_interval)  # Wait before checking again

    if not result["found"]:
        return {}
    else:
        return result


def generate_css_selector(driver, element):
    """
    Generate a CSS selector for the given element.

    Args:
        driver: Selenium WebDriver instance
        element: WebElement to generate a selector for

    Returns:
        str: CSS selector for the element
    """
    try:
        # Try to get a unique ID if available
        element_id = element.get_attribute("id")
        if element_id:
            return f"#{element_id}"

        # Try to get a unique class if available
        element_class = element.get_attribute("class")
        if element_class:
            # Check if this class is unique
            elements_with_class = driver.find_elements(By.CLASS_NAME, element_class)
            if len(elements_with_class) == 1:
                return f".{element_class}"

        # Generate a selector based on tag and attributes
        tag_name = element.tag_name
        selector = tag_name

        # Add attributes to make the selector more specific
        for attr in ["id", "name", "class", "type", "value"]:
            attr_value = element.get_attribute(attr)
            if attr_value:
                if attr == "class":
                    # Handle multiple classes
                    classes = attr_value.split()
                    for cls in classes:
                        selector += f".{cls}"
                else:
                    selector += f"[{attr}='{attr_value}']"

        # If we still don't have a unique selector, add position
        if len(driver.find_elements(By.CSS_SELECTOR, selector)) > 1:
            # Get all elements with the same tag
            siblings = driver.find_elements(By.XPATH, f"//{tag_name}")
            for i, sibling in enumerate(siblings):
                if sibling == element:
                    selector += f":nth-of-type({i+1})"
                    break

        return selector
    except:
        # Fallback to a simple tag selector
        return element.tag_name


def find_and_click_button(driver, button_text, timeout=30, check_interval=0.5):
    """
    Find a button with the specified text and click it using multiple methods.

    Args:
        driver: Selenium WebDriver instance
        button_text: Text to search for on the button
        timeout: Maximum time to wait for the button (in seconds)
        check_interval: Time between checks (in seconds)

    Returns:
        bool: True if the button was found and clicked successfully, False otherwise
    """
    print(f"\n=== Attempting to Find and Click Button with Text: '{button_text}' ===")

    # Find the button with the specified text
    button = check_text_on_page(
        driver, button_text, timeout=timeout, check_interval=check_interval
    )

    if not button.get("found"):
        print(f"✗ Button with text '{button_text}' not found!")
        return False

    print(f"Button found with text: {button['text']}")

    # Try multiple approaches to click the button
    success = False

    # Approach 1: Use the specific CSS selector from the HTML
    if not success:
        try:
            print("\n[Method 1] Trying CSS selector approach...")
            button_element = driver.find_element(
                By.CSS_SELECTOR, "button.el-button.el-button--primary[type='button']"
            )
            button_element.click()
            print("✓ CSS selector click successful!")
            success = True

            # Wait for the page to load after clicking
            time.sleep(5)
        except Exception as e:
            print(f"✗ CSS selector approach failed: {str(e)}")

    # Approach 2: Try using JavaScript
    if not success:
        try:
            print("\n[Method 2] Trying JavaScript approach...")
            driver.execute_script(
                "document.querySelector('button.el-button.el-button--primary[type=\"button\"]').click();"
            )
            print("✓ JavaScript click successful!")
            success = True

            # Wait for the page to load after clicking
            time.sleep(5)
        except Exception as js_error:
            print(f"✗ JavaScript approach failed: {str(js_error)}")

    # Approach 3: Try using pixel coordinates as a last resort
    if not success:
        try:
            print("\n[Method 3] Trying pixel coordinates approach...")
            # Get the location and size of the element
            location = button["location"]
            size = button["size"]

            # Calculate the center point of the element
            x = location["x"] + (size["width"] / 2)
            y = location["y"] + (size["height"] / 2)

            print(f"Clicking at coordinates: x={x}, y={y}")

            # Use ActionChains to move to the element and click it
            actions = ActionChains(driver)
            actions.move_by_offset(x, y).click().perform()

            print("✓ Coordinate-based click successful!")
            success = True

            # Reset the mouse position
            actions.move_by_offset(-x, -y).perform()

            # Wait for the page to load after clicking
            time.sleep(5)
        except Exception as coord_error:
            print(f"✗ Coordinate approach failed: {str(coord_error)}")

    if not success:
        print(f"\n✗ All methods to click the '{button_text}' button failed!")
        return False

    return True
