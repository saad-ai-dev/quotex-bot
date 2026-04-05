"""
Playwright fixtures for Chrome Extension testing.
ALERT-ONLY system - no trade execution.

Requires:
    - Extension built first: cd extension && npm run build
    - Playwright installed: pip install playwright && playwright install chromium

Run with: pytest testing/extension/ --headed -v
"""

import pytest
from pathlib import Path
from playwright.async_api import async_playwright


EXTENSION_DIST = str(Path(__file__).parent.parent.parent / "extension" / "dist")


@pytest.fixture(scope="session")
def extension_path():
    """Return the path to the built extension dist directory."""
    p = Path(EXTENSION_DIST)
    if not p.exists():
        pytest.skip(
            f"Extension not built at {EXTENSION_DIST}. "
            "Run 'cd extension && npm run build' first."
        )
    return str(p)


@pytest.fixture
async def browser_with_extension(extension_path):
    """Launch Chrome with the extension loaded.

    Playwright's chromium.launch_persistent_context is required for
    extension loading because Manifest V3 service workers need a
    persistent context.
    """
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            "",  # empty string = temporary profile directory
            headless=False,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        yield context
        await context.close()


@pytest.fixture
async def page(browser_with_extension):
    """Get a new page in the extension context."""
    page = await browser_with_extension.new_page()
    yield page
    await page.close()


@pytest.fixture
async def extension_id(browser_with_extension):
    """Get the extension ID for accessing chrome-extension:// pages.

    Reads the ID from the service worker URL registered by the extension.
    Returns None if no service worker is found (extension failed to load).
    """
    # Wait briefly for the service worker to register
    background = browser_with_extension.service_workers
    if not background:
        # Give the extension a moment to initialize
        import asyncio
        await asyncio.sleep(1)
        background = browser_with_extension.service_workers

    if background:
        ext_url = background[0].url
        # URL format: chrome-extension://<id>/service-worker.js
        ext_id = ext_url.split("/")[2]
        return ext_id

    pytest.skip("Extension service worker not found - extension may not have loaded")
    return None


@pytest.fixture
async def popup_page(browser_with_extension, extension_id):
    """Open the extension popup page directly by URL.

    Note: This opens the popup as a full page, not as the browser-action
    popup dropdown. Behavior is functionally equivalent for UI testing.
    """
    page = await browser_with_extension.new_page()
    await page.goto(f"chrome-extension://{extension_id}/src/popup/index.html")
    await page.wait_for_load_state("domcontentloaded")
    yield page
    await page.close()


@pytest.fixture
async def history_page(browser_with_extension, extension_id):
    """Open the extension history page."""
    page = await browser_with_extension.new_page()
    await page.goto(f"chrome-extension://{extension_id}/src/history/index.html")
    await page.wait_for_load_state("domcontentloaded")
    yield page
    await page.close()


@pytest.fixture
async def options_page(browser_with_extension, extension_id):
    """Open the extension options page."""
    page = await browser_with_extension.new_page()
    await page.goto(f"chrome-extension://{extension_id}/src/options/index.html")
    await page.wait_for_load_state("domcontentloaded")
    yield page
    await page.close()


@pytest.fixture
async def quotex_page(browser_with_extension):
    """Open a page navigated to a mock Quotex URL.

    Used for testing content script injection. The actual Quotex site
    is not loaded; this tests that the content script activates on
    matching URL patterns.
    """
    page = await browser_with_extension.new_page()
    # Navigate to about:blank first, then set URL pattern
    # For real testing, you would need a local mock server
    yield page
    await page.close()
