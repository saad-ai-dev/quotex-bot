"""
Playwright tests for Chrome Extension History Page.
ALERT-ONLY system - no trade execution testing.

The history page displays a log of past alerts with filtering,
pagination, and summary statistics.

Requirements:
    - Extension must be built: cd extension && npm run build
    - Run with: pytest testing/extension/test_history_page.py --headed -v
"""

import pytest


pytestmark = pytest.mark.asyncio


class TestHistoryPage:
    """Test the extension history/alert log page."""

    async def test_history_page_renders(self, history_page):
        """History page HTML loads and the UI framework mounts.

        TODO: Verify the root mount element is present. Check for the
        page heading (e.g., "Alert History"). Confirm the alert table
        or list container is rendered.
        """
        assert history_page.url.startswith("chrome-extension://")
        # TODO: Update selectors once history page structure is finalized
        # heading = history_page.locator("h1, h2")
        # assert await heading.count() >= 1

    async def test_filter_by_market_type(self, history_page):
        """Filtering alerts by market type (live/otc) works.

        TODO: Locate the market type filter dropdown or radio group.
        Select 'live' and verify only live-market alerts are displayed.
        Select 'otc' and verify only OTC alerts are shown.
        Select 'all' and verify all alerts reappear.
        """
        # TODO: Implement when history page UI is built
        # filter_el = history_page.locator("[data-testid='filter-market-type']")
        # await filter_el.select_option("live")
        # rows = history_page.locator("[data-testid='alert-row']")
        # for i in range(await rows.count()):
        #     market = await rows.nth(i).locator(".market-type").text_content()
        #     assert market == "live"

    async def test_filter_by_expiry(self, history_page):
        """Filtering alerts by expiry duration (1m/2m/3m) works.

        TODO: Locate the expiry filter. Select '1m' and verify
        displayed alerts all have 1-minute expiry. Repeat for 2m, 3m.
        """
        # TODO: Implement when history page UI is built
        # filter_el = history_page.locator("[data-testid='filter-expiry']")
        # await filter_el.select_option("1m")
        # rows = history_page.locator("[data-testid='alert-row']")
        # count = await rows.count()
        # assert count >= 0  # May be 0 if no matching alerts

    async def test_filter_by_outcome(self, history_page):
        """Filtering alerts by outcome (win/loss/pending) works.

        TODO: Locate the outcome filter. Select 'win' and verify only
        winning alerts are shown. Select 'loss' for losing ones.
        Select 'pending' for alerts still awaiting resolution.
        """
        # TODO: Implement when history page UI is built
        # filter_el = history_page.locator("[data-testid='filter-outcome']")
        # await filter_el.select_option("win")
        # rows = history_page.locator("[data-testid='alert-row']")
        # for i in range(await rows.count()):
        #     outcome = await rows.nth(i).locator(".outcome").text_content()
        #     assert outcome.lower() == "win"

    async def test_pagination_controls(self, history_page):
        """Pagination next/prev buttons navigate between pages.

        TODO: Inject enough mock alerts to span multiple pages.
        Verify 'Next' button advances to page 2. Verify 'Previous'
        returns to page 1. Verify page indicator updates correctly.
        Verify 'Next' is disabled on the last page.
        """
        # TODO: Implement when history page UI is built
        # next_btn = history_page.locator("[data-testid='pagination-next']")
        # prev_btn = history_page.locator("[data-testid='pagination-prev']")
        # page_label = history_page.locator("[data-testid='pagination-label']")
        # assert "1" in await page_label.text_content()

    async def test_summary_stats_display(self, history_page):
        """Summary statistics section displays correctly.

        TODO: Verify the summary stats section exists and shows:
        - Total alerts count
        - Win rate percentage
        - Average confidence of alerts
        - Alerts per session or per day
        When no alerts exist, verify stats show zeroes or dashes.
        """
        # TODO: Implement when history page UI is built
        # stats = history_page.locator("[data-testid='summary-stats']")
        # assert await stats.is_visible()
        # total = history_page.locator("[data-testid='stat-total-alerts']")
        # assert await total.text_content() is not None

    async def test_date_range_filter(self, history_page):
        """Date range filter restricts displayed alerts.

        TODO: Locate the date range picker (start and end date inputs).
        Set a date range and verify only alerts within that range are
        displayed. Clear the filter and verify all alerts return.
        """
        # TODO: Implement when history page UI is built
        # start_input = history_page.locator("[data-testid='date-start']")
        # end_input = history_page.locator("[data-testid='date-end']")
        # await start_input.fill("2025-01-01")
        # await end_input.fill("2025-12-31")
        # apply_btn = history_page.locator("[data-testid='date-filter-apply']")
        # await apply_btn.click()

    async def test_empty_state_display(self, history_page):
        """Empty state message shows when no alerts exist.

        TODO: With no alerts in chrome.storage, verify that the history
        page shows an empty-state message (e.g., "No alerts recorded yet")
        instead of an empty table. Verify the message is user-friendly.
        """
        # TODO: Implement when history page UI is built
        # empty_msg = history_page.locator("[data-testid='empty-state']")
        # assert await empty_msg.is_visible()
        # text = await empty_msg.text_content()
        # assert "no alerts" in text.lower() or "empty" in text.lower()
