import unittest
from pathlib import Path

from store_manager.core import ProductInput
from store_manager.live_draft import (
    EXISTING_PRODUCT_DRAFT_PRESENT,
    EXISTING_PRODUCT_INITIAL_SUBMISSION,
    EXISTING_PRODUCT_UPDATE_AVAILABLE,
    UNKNOWN_PARTNER_CENTER_STATE,
    LiveGateError,
    PlaywrightPartnerCenterPort,
    SelectorMap,
    SubmissionStateObservation,
    SubmissionStateResult,
    classify_existing_product_submission_state,
    reconcile_ambiguous_initial_submission,
)


class _ReadOnlyLocator:
    def __init__(self, items=(), *, href="", visible=True):
        self._items = list(items)
        self._href = href
        self._visible = visible

    def all(self):
        return list(self._items)

    def count(self):
        return len(self._items)

    def is_visible(self):
        return self._visible

    def get_attribute(self, name):
        return self._href if name == "href" else None


class _InitialSubmissionPage:
    def __init__(self):
        self.url = "https://partner.microsoft.com/en-us/dashboard/apps-and-games/overview"
        self.visited = []
        self.identity_values = {
            "Folder Automation Engine",
            "9P99MJX1R4V6",
            "OkinawaDesktopTools.FolderAutomationEngine",
            "CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
        }

    def goto(self, url, wait_until=None, timeout=None):
        self.url = url
        self.visited.append(url)

    def locator(self, selector):
        if selector == 'input[type="file"]' and "/submissions/" in self.url and "/packages" in self.url:
            return _ReadOnlyLocator((_ReadOnlyLocator(),))
        if selector in {"input[type='password']", "a[href]", "table tbody tr"}:
            return _ReadOnlyLocator()
        return _ReadOnlyLocator()

    def get_by_text(self, text, exact=True):
        visible = False
        if "/identity" in self.url:
            visible = text in self.identity_values
        elif "/submissions/" in self.url and "/packages" in self.url:
            visible = text == "Packages"
        elif "/overview" in self.url:
            visible = text == "Start submission"
        elif "/managepackages" in self.url:
            visible = text == "Your active packages are listed below."
        item = _ReadOnlyLocator(visible=visible)
        return _ReadOnlyLocator((item,) if exact and visible else ())


class _StartButton:
    def __init__(self): self.clicked=0
    def count(self): return 1
    def is_visible(self): return True
    def click(self,timeout=None): self.clicked+=1

class _StartPage:
    def __init__(self):
        self.url="https://partner.microsoft.com/en-us/dashboard/products/9P99MJX1R4V6/overview"
        self.button=_StartButton()
    def get_by_text(self,text,exact=True):
        if text=="Start submission" and exact: return self.button
        return _ReadOnlyLocator()
    def locator(self,selector): return _ReadOnlyLocator()
    def wait_for_timeout(self,ms): return None

class ExistingProductSubmissionStateTests(unittest.TestCase):
    def test_existing_product_without_package_or_draft_is_initial_submission(self):
        result = classify_existing_product_submission_state(
            SubmissionStateObservation(
                store_product_id="9P99MJX1R4V6",
                existing_product_verified=True,
                start_submission_visible=True,
                current_packages_page_verified=True,
                active_package_count=0,
            )
        )
        self.assertEqual(result.state, EXISTING_PRODUCT_INITIAL_SUBMISSION)
        self.assertEqual(result.required_submission_kind, "new")
        self.assertEqual(result.hold_code, "HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED")

    def test_existing_draft_packages_url_connects_to_that_draft(self):
        result = classify_existing_product_submission_state(
            SubmissionStateObservation(
                store_product_id="9P99MJX1R4V6",
                existing_product_verified=True,
                draft_packages_urls=(
                    "https://partner.microsoft.com/en-us/dashboard/products/9P99MJX1R4V6/"
                    "submissions/1152921505702219486/packages",
                ),
            )
        )
        self.assertEqual(result.state, EXISTING_PRODUCT_DRAFT_PRESENT)
        self.assertEqual(result.draft_id, "1152921505702219486")
        self.assertTrue(result.draft_url.endswith("/submissions/1152921505702219486"))
        self.assertEqual(result.hold_code, "")

    def test_published_product_with_start_update_is_update_route(self):
        result = classify_existing_product_submission_state(
            SubmissionStateObservation(
                store_product_id="9P99MJX1R4V6",
                existing_product_verified=True,
                start_update_visible=True,
                current_packages_page_verified=True,
                active_package_count=1,
            )
        )
        self.assertEqual(result.state, EXISTING_PRODUCT_UPDATE_AVAILABLE)
        self.assertEqual(result.required_submission_kind, "update")
        self.assertEqual(result.hold_code, "HOLD_UPDATE_SUBMISSION_ROUTE_REQUIRED")

    def test_conflicting_or_incomplete_signals_hold_unknown(self):
        cases = (
            SubmissionStateObservation("9P99MJX1R4V6", True),
            SubmissionStateObservation(
                "9P99MJX1R4V6",
                True,
                start_submission_visible=True,
                start_update_visible=True,
                current_packages_page_verified=True,
                active_package_count=0,
            ),
            SubmissionStateObservation(
                "9P99MJX1R4V6",
                True,
                draft_packages_urls=(
                    "https://partner.microsoft.com/en-us/dashboard/products/OTHER/"
                    "submissions/123/packages",
                ),
            ),
        )
        for observation in cases:
            with self.subTest(observation=observation):
                result = classify_existing_product_submission_state(observation)
                self.assertEqual(result.state, UNKNOWN_PARTNER_CENTER_STATE)
                self.assertEqual(result.hold_code, "HOLD_UNKNOWN_SUBMISSION_STATE")

    def test_reconcile_ambiguous_attempt_recovers_existing_draft_without_retry(self):
        status, retry_candidate = reconcile_ambiguous_initial_submission(
            SubmissionStateResult(
                EXISTING_PRODUCT_DRAFT_PRESENT,
                draft_id="12345",
                draft_url="https://partner.microsoft.com/en-us/dashboard/products/9P99MJX1R4V6/submissions/12345",
            )
        )
        self.assertEqual(status, "INITIAL_SUBMISSION_DRAFT_PRESENT_RECOVERED")
        self.assertFalse(retry_candidate)

    def test_reconcile_ambiguous_attempt_requires_new_approval_if_still_initial(self):
        status, retry_candidate = reconcile_ambiguous_initial_submission(
            SubmissionStateResult(
                EXISTING_PRODUCT_INITIAL_SUBMISSION,
                required_submission_kind="new",
            )
        )
        self.assertEqual(status, "INITIAL_SUBMISSION_NOT_OBSERVED_RETRY_REQUIRES_NEW_APPROVAL")
        self.assertTrue(retry_candidate)

    def test_reconcile_ambiguous_attempt_holds_unknown_state(self):
        status, retry_candidate = reconcile_ambiguous_initial_submission(
            SubmissionStateResult(
                UNKNOWN_PARTNER_CENTER_STATE,
                hold_code="HOLD_UNKNOWN_SUBMISSION_STATE",
            )
        )
        self.assertEqual(status, "HOLD_AMBIGUOUS_WRITE")
        self.assertFalse(retry_candidate)

    def test_pinned_draft_is_verified_by_direct_read_only_packages_probe(self):
        page = _InitialSubmissionPage()
        port = PlaywrightPartnerCenterPort(
            page,
            SelectorMap({"schema_version": 3, "routes": {}}),
            Path("."),
        )
        product = ProductInput(
            "app",
            "Folder Automation Engine",
            "Offline utility",
            store_product_id="9P99MJX1R4V6",
            identity_name="OkinawaDesktopTools.FolderAutomationEngine",
            identity_publisher="CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
            submission_kind="new",
            draft_id="1152921505702219486",
        )
        result = port.inspect_existing_product_submission_state(product)
        self.assertEqual(result.state, EXISTING_PRODUCT_DRAFT_PRESENT)
        self.assertEqual(result.draft_id, "1152921505702219486")
        self.assertTrue(page.visited[-1].endswith("/submissions/1152921505702219486/packages"))
        self.assertFalse(any(url.endswith("/managepackages") for url in page.visited))

    def test_start_initial_submission_creates_only_draft_after_exact_recheck(self):
        page=_StartPage()
        port=PlaywrightPartnerCenterPort(
            page,
            SelectorMap({"schema_version":3,"routes":{}}),
            Path("."),
        )
        states=iter((
            SubmissionStateResult(
                EXISTING_PRODUCT_INITIAL_SUBMISSION,
                required_submission_kind="new",
                hold_code="HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED",
            ),
            SubmissionStateResult(
                EXISTING_PRODUCT_DRAFT_PRESENT,
                draft_id="12345",
                draft_url="https://partner.microsoft.com/en-us/dashboard/products/9P99MJX1R4V6/submissions/12345",
            ),
        ))
        port.inspect_existing_product_submission_state=lambda product: next(states)
        product=ProductInput(
            "app","Folder Automation Engine","Offline utility",
            store_product_id="9P99MJX1R4V6",
            submission_kind="new",
        )
        context=port.start_initial_submission_draft(product)
        self.assertEqual(context.draft_id,"12345")
        self.assertEqual(page.button.clicked,1)

    def test_start_initial_submission_rejects_wrong_kind_before_click(self):
        page=_StartPage()
        port=PlaywrightPartnerCenterPort(
            page,
            SelectorMap({"schema_version":3,"routes":{}}),
            Path("."),
        )
        product=ProductInput(
            "app","Folder Automation Engine","Offline utility",
            store_product_id="9P99MJX1R4V6",
            submission_kind="update",
        )
        with self.assertRaisesRegex(LiveGateError,"submission_kind=new"):
            port.start_initial_submission_draft(product)
        self.assertEqual(page.button.clicked,0)

    def test_live_adapter_reads_initial_state_and_never_needs_a_click_method(self):
        page = _InitialSubmissionPage()
        port = PlaywrightPartnerCenterPort(
            page,
            SelectorMap({"schema_version": 3, "routes": {}}),
            Path("."),
        )
        product = ProductInput(
            "app",
            "Folder Automation Engine",
            "Offline utility",
            store_product_id="9P99MJX1R4V6",
            identity_name="OkinawaDesktopTools.FolderAutomationEngine",
            identity_publisher="CN=46263F21-A700-41DB-8C9B-114C22FB82FC",
            submission_kind="new",
        )
        result = port.inspect_existing_product_submission_state(product)
        self.assertEqual(result.state, EXISTING_PRODUCT_INITIAL_SUBMISSION)
        self.assertEqual(result.required_submission_kind, "new")
        self.assertTrue(page.visited[-1].endswith("/managepackages"))
        with self.assertRaisesRegex(LiveGateError, "HOLD_INITIAL_SUBMISSION_ROUTE_REQUIRED"):
            port.verify_product_and_draft(product)


if __name__ == "__main__":
    unittest.main()
