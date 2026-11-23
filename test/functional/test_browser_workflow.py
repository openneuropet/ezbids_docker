"""Opt-in tests of the containerized application, using only browser mutations."""

import http.server
import json
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from workflow import inspect_download, load_profile, metadata_value, validator_errors


def selector(test_id):
    return f'[data-testid="{test_id}"]'


class BlockExternalRequests(http.server.BaseHTTPRequestHandler):
    def do_CONNECT(self):
        try:
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_GET = do_CONNECT
    do_POST = do_CONNECT

    def log_message(self, *_args):
        pass


class Browser:
    def __init__(self, driver, config, artifacts):
        self.driver, self.config, self.artifacts = driver, config, artifacts
        self.wait = WebDriverWait(
            driver, 30, ignored_exceptions=(StaleElementReferenceException,)
        )

    def visible(self, css):
        return self.wait.until(
            lambda d: next(
                (
                    element
                    for element in d.find_elements(By.CSS_SELECTOR, css)
                    if element.is_displayed()
                ),
                False,
            ),
            message=f"Element not visible: {css}",
        )

    def click(self, css):
        element = self.visible(css)
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});", element
        )
        self.wait.until(lambda _d: element.is_enabled())
        element.click()

    def fill(self, css, value):
        element = self.visible(css)
        if element.tag_name not in ("input", "textarea"):
            element = element.find_element(By.CSS_SELECTOR, "input,textarea")
        element.send_keys(Keys.CONTROL, "a", Keys.NULL)
        element.send_keys(Keys.BACKSPACE)
        if value != "":
            element.send_keys(str(value))
        element.send_keys(Keys.TAB)

    def step(self, name):
        self.visible(f'{selector("wizard-step")}[data-step="{name}"]')

    def next(self, name):
        self.click(selector("wizard-next"))
        self.step(name)
        self.checkpoint(name)

    def checkpoint(self, name):
        self.driver.save_screenshot(str(self.artifacts / f"{name}.png"))
        print(f"{self.artifacts.name}: {name}", flush=True)

    def wait_for_conversion(self, test_id):
        def completed(driver):
            body = driver.find_element(By.TAG_NAME, "body").text
            assert (
                "failed to run preprocess" not in body
                and "Failed to convert to BIDS" not in body
            ), body
            return driver.find_elements(By.CSS_SELECTOR, selector(test_id))

        WebDriverWait(
            self.driver,
            self.config["timeout"],
            ignored_exceptions=(StaleElementReferenceException,),
        ).until(completed)

    def choose(self, css, value, *, contains=False):
        self.click(css)

        def option(driver):
            for element in driver.find_elements(
                By.CSS_SELECTOR, ".el-select-dropdown__item"
            ):
                text = element.text.strip()
                if element.is_displayed() and (
                    value in text if contains else value == text
                ):
                    return element
            return False

        self.wait.until(option, message=f"Option {value!r} not found in {css}").click()

    def fetch(self, path, *, download=False):
        # Read-only evidence requests run in the browser with its actual cookies.
        result = self.driver.execute_async_script(
            """
            const [base, path, download, done] = arguments;
            (async () => {
                let url = base + path;
                if (download) {
                    const id = location.hash.slice(1);
                    const tokenResponse = await fetch(base + '/download/' + id + '/token', {credentials:'include'});
                    if (!tokenResponse.ok) throw new Error('Token HTTP ' + tokenResponse.status);
                    const token = await tokenResponse.text();
                    url = base + '/download/' + id + '/' + path + '?token=' + encodeURIComponent(token);
                }
                const response = await fetch(url, {credentials:'include'});
                done({status:response.status, text:await response.text()});
            })().catch(error => done({error:String(error)}));
        """,
            self.config["api"],
            path,
            download,
        )
        assert "error" not in result, result
        return result

    def report(self, path):
        result = self.fetch(path, download=True)
        assert result["status"] == 200, f"{path}: HTTP {result['status']}"
        (self.artifacts / path).write_text(result["text"])
        return json.loads(result["text"])

    def register(self):
        email = f"browser-{uuid.uuid4().hex}@example.test"
        password = f"Phantom-{uuid.uuid4().hex}"
        self.driver.get(self.config["ui"] + "register")
        self.fill(selector("register-name"), "Phantom functional test")
        self.fill(selector("register-email"), email)
        self.fill(selector("register-password"), password)
        self.fill(selector("register-confirm"), password)
        self.click(selector("register-submit"))
        self.visible(selector("sessions-page"))
        self.visible(selector("sessions-empty"))
        return email, password


@pytest.fixture(scope="module")
def config():
    required = (
        "EZBIDS_E2E_UI_URL",
        "EZBIDS_E2E_API_URL",
        "EZBIDS_E2E_DATA",
        "EZBIDS_E2E_ARTIFACTS",
    )
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        pytest.fail("Run test/functional/run.sh; missing " + ", ".join(missing))
    ui, api = os.environ[required[0]].rstrip("/") + "/", os.environ[required[1]].rstrip(
        "/"
    )
    for url in (ui, api):
        parsed = urlparse(url)
        assert parsed.scheme == "http" and parsed.hostname in (
            "localhost",
            "127.0.0.1",
        ), url
    data = Path(os.environ[required[2]]).expanduser().resolve(strict=True)
    assert data.is_dir() and any(data.rglob("*")), "Empty upload fixture"
    artifacts = Path(os.environ[required[3]]).resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    profile = load_profile(
        os.environ.get(
            "EZBIDS_E2E_PROFILE", Path(__file__).parent / "profiles/pet-phantom.json"
        )
    )
    return {
        "ui": ui,
        "api": api,
        "data": data,
        "artifacts": artifacts,
        "profile": profile,
        "timeout": int(os.environ.get("EZBIDS_E2E_TIMEOUT", "600")),
    }


@pytest.fixture
def browser_factory(config):
    browsers = []
    proxy = http.server.ThreadingHTTPServer(("127.0.0.1", 0), BlockExternalRequests)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()

    def create(name):
        artifacts = Path(tempfile.mkdtemp(prefix=name + "-", dir=config["artifacts"]))
        downloads = artifacts / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        options = webdriver.ChromeOptions()
        if os.environ.get("EZBIDS_E2E_HEADED") != "true":
            options.add_argument("--headless=new")
        if os.environ.get("EZBIDS_E2E_BROWSER_BINARY"):
            options.binary_location = os.environ["EZBIDS_E2E_BROWSER_BINARY"]
        for argument in (
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-sync",
            "--no-first-run",
            "--disable-dev-shm-usage",
        ):
            options.add_argument(argument)
        options.add_argument(f"--proxy-server=http://127.0.0.1:{proxy.server_port}")
        options.add_argument("--proxy-bypass-list=localhost;127.0.0.1")
        preferences = {
            "download.default_directory": str(downloads),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", preferences)
        driver_path = os.environ.get("CHROMEDRIVER")
        service = Service(
            executable_path=driver_path,
            log_output=str(artifacts / "chromedriver.log"),
            service_args=["--log-level=WARNING"],
        )
        driver = webdriver.Chrome(options=options, service=service)
        driver.set_window_size(1440, 1100)
        driver.set_script_timeout(40)
        browser = Browser(driver, config, artifacts)
        browsers.append(browser)
        return browser

    yield create
    cleanup_errors = []
    try:
        for browser in browsers:
            try:
                browser.checkpoint("last-page")
                # No cookies, storage, headers, or network tokens are written to diagnostics.
                (browser.artifacts / "last-page.txt").write_text(
                    browser.driver.find_element(By.TAG_NAME, "body").text
                )
            except Exception as error:
                cleanup_errors.append(str(error))
            finally:
                try:
                    browser.driver.quit()
                except Exception as error:
                    cleanup_errors.append(str(error))
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)
    assert not cleanup_errors, cleanup_errors


def edit_metadata(browser, series):
    browser.click(selector("metadata-open"))
    dialog = browser.visible(selector("metadata-dialog"))
    for field, configured in series.get("metadata", {}).items():
        css = f'{selector("metadata-dialog")} {selector("metadata-field")}[data-field="{field}"]'
        item = browser.visible(css)
        value = metadata_value(configured)
        desired_type = configured.get("type") if isinstance(configured, dict) else None
        if (
            desired_type is None
            and item.get_attribute("data-input-type") == "select-type"
        ):
            desired_type = (
                "array"
                if isinstance(value, list)
                else (
                    "boolean"
                    if isinstance(value, bool)
                    else "number" if isinstance(value, (int, float)) else "string"
                )
            )
        if desired_type and (
            isinstance(configured, dict)
            or item.get_attribute("data-value-type") != desired_type
        ):
            browser.choose(css + " " + selector("metadata-type"), desired_type)
            item = browser.visible(css)
        kind = item.get_attribute("data-input-type")
        if kind in ("select-boolean", "select-enum"):
            browser.choose(
                css + " .el-select",
                str(value),
            )
        else:
            text = (
                ",".join(str(part) for part in value)
                if isinstance(value, list)
                else str(value)
            )
            browser.fill(css + " input:not([readonly]), " + css + " textarea", text)
    browser.click(selector("metadata-submit"))
    browser.wait.until(lambda _d: not dialog.is_displayed())


@pytest.mark.parametrize("identity", ["guest", "account"])
def test_upload_edit_finalize_validate_and_download(config, browser_factory, identity):
    browser = browser_factory(identity)
    profile = config["profile"]
    credentials = browser.register() if identity == "account" else None
    if credentials:
        browser.click(selector("sessions-new"))
    else:
        browser.driver.get(config["ui"] + "convert")
    browser.step("upload")
    # WebDriver sends a directory through the same file input used by Select Directory.
    browser.driver.find_element(
        By.CSS_SELECTOR, selector("upload-directory")
    ).send_keys(str(config["data"]))
    browser.wait_for_conversion("upload-analysis-complete")
    session_id = browser.driver.current_url.split("#")[-1]
    assert re.fullmatch(r"[a-f0-9]{24}", session_id), browser.driver.current_url
    original = browser.report("ezBIDS_core.json")
    assert original.get("objects"), "Preprocessing produced no acquisitions"
    edits = profile.get("expected_metadata_edits", [])
    assert edits, "Profile must exercise at least one missing metadata field"
    raw_sidecars = [
        item["sidecar"]
        for obj in original["objects"]
        for item in obj.get("items", [])
        if item.get("name") == "json" and isinstance(item.get("sidecar"), dict)
    ]
    assert raw_sidecars, "Preprocessing produced no JSON sidecars"
    for field in edits:
        assert any(field in series.get("metadata", {}) for series in profile["series"])
        assert any(
            sidecar.get(field) in (None, "") for sidecar in raw_sidecars
        ), f"{field} was already present"
    browser.checkpoint("analysis-complete")
    browser.next("description")
    browser.fill(selector("dataset-name"), profile["dataset_name"])
    browser.fill(
        selector("dataset-readme"),
        profile.get("readme", "Public phantom browser functional test."),
    )
    browser.next("subject")
    subject_inputs = browser.driver.find_elements(
        By.CSS_SELECTOR, selector("subject-label")
    )
    assert len(subject_inputs) == len(profile["subjects"]), "Unexpected subject count"
    for index, subject in enumerate(profile["subjects"]):
        browser.fill(
            f'{selector("subject-label")}[data-subject-index="{index}"]',
            subject["subject"],
        )
        for session_index, label in enumerate(subject.get("sessions", [])):
            browser.fill(
                f'{selector("session-label")}[data-subject-index="{index}"][data-session-index="{session_index}"]',
                label,
            )
        for element in browser.driver.find_elements(
            By.CSS_SELECTOR,
            f'{selector("subject-exclude")}[data-subject-index="{index}"] input',
        ):
            assert not element.is_selected(), "Fixture subject was excluded"
    browser.next("seriespage")
    rows = browser.driver.find_elements(By.CSS_SELECTOR, selector("series-row"))
    assert len(rows) == len(
        profile["series"]
    ), "Unexpected series; define every series in the profile"
    for series in profile["series"]:
        row = next(
            (
                row
                for row in rows
                if (
                    re.fullmatch(
                        series["description_pattern"],
                        row.get_attribute("data-series-description"),
                    )
                    if "description_pattern" in series
                    else row.get_attribute("data-series-description")
                    == series["description"]
                )
            ),
            None,
        )
        assert row is not None, f"Series not found: {series['description']}"
        row.click()
        current = browser.visible(selector("series-datatype") + " input").get_attribute(
            "value"
        )
        if current != series["datatype"]:
            browser.choose(
                selector("series-datatype"),
                series.get("datatype_label", "PET"),
                contains=True,
            )
        for entity, value in series.get("entities", {}).items():
            browser.fill(f'{selector("series-entity")}[data-entity="{entity}"]', value)
        edit_metadata(browser, series)
    browser.next("event")
    browser.next("object")
    object_rows = browser.driver.find_elements(By.CSS_SELECTOR, selector("object-row"))
    assert object_rows, "No acquisitions on Dataset Review"
    for checkbox in browser.driver.find_elements(
        By.CSS_SELECTOR, selector("object-exclude") + " input"
    ):
        assert not checkbox.is_selected(), "Fixture acquisition was excluded"
    browser.next("deface")
    browser.next("participant")
    browser.next("finalize")
    include_excluded = browser.visible(selector("finalize-include-excluded"))
    if include_excluded.find_element(
        By.CSS_SELECTOR, 'input[type="checkbox"]'
    ).is_selected():
        browser.click(selector("finalize-include-excluded"))
    assert not include_excluded.find_element(
        By.CSS_SELECTOR, 'input[type="checkbox"]'
    ).is_selected()
    browser.click(selector("finalize-submit"))
    browser.wait_for_conversion("finalize-completed")
    browser.visible(selector("validator-report"))
    browser.wait.until(
        lambda d: d.find_element(
            By.CSS_SELECTOR, selector("validator-report")
        ).text.strip()
    )
    report = browser.report("validator.json")
    errors = validator_errors(report)
    assert errors == [], json.dumps(errors, indent=2)
    finalized = browser.report("finalized.json")
    assert finalized["includeExcluded"] is False
    assert any(
        obj.get("_type") not in (None, "exclude") for obj in finalized["objects"]
    ), "No included output acquisitions"
    browser.click(selector("bids-download"))

    def completed_download(_driver):
        files = list((browser.artifacts / "downloads").glob("*.zip"))
        if files and not list((browser.artifacts / "downloads").glob("*.crdownload")):
            return files[0]
        return False

    archive = WebDriverWait(browser.driver, config["timeout"]).until(completed_download)
    images = inspect_download(archive, profile)
    (browser.artifacts / "result.json").write_text(
        json.dumps(
            {
                "session": session_id,
                "identity": identity,
                "validator_errors": 0,
                "images": images,
                "metadata_edits": edits,
            },
            indent=2,
        )
    )
    if credentials:
        check_account_history(browser, browser_factory, credentials, session_id)
    else:
        browser.driver.refresh()
        browser.step("finalize")
        browser.visible(selector("finalize-completed"))


def check_account_history(browser, browser_factory, credentials, session_id):
    browser.click(selector("wizard-my-sessions"))
    browser.visible(f'{selector("sessions-open")}[data-session-id="{session_id}"]')
    browser.click(selector("sessions-logout"))
    browser.fill(selector("login-email"), credentials[0])
    browser.fill(selector("login-password"), credentials[1])
    browser.click(selector("login-submit"))
    own_session = f'{selector("sessions-open")}[data-session-id="{session_id}"]'
    browser.visible(own_session)
    browser.click(own_session)
    browser.step("finalize")
    browser.visible(selector("finalize-completed"))
    stranger = browser_factory("other-account")
    stranger.register()
    assert not stranger.driver.find_elements(By.CSS_SELECTOR, own_session)
    stranger.driver.get(stranger.config["ui"] + "convert#" + session_id)
    stranger.visible(selector("sessions-page"))
    stranger.visible(selector("sessions-empty"))
    denied = stranger.fetch("/session/" + session_id)
    assert denied["status"] in (403, 404), "Other account could read an owner's session"
    assert not stranger.driver.find_elements(
        By.CSS_SELECTOR, selector("finalize-completed")
    )
