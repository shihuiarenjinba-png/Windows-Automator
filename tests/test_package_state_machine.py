import unittest

from store_manager.live_draft import (
    PackageRuntimeObservation,
    package_next_action,
    reconcile_file_chooser_timeout,
    session_expiry_recovery_next_action,
)
from store_manager.restricted_capabilities import RUNFULLTRUST_PACKAGE_WARNING


class PackageStateMachineTests(unittest.TestCase):
    def test_known_lifecycle_is_deterministic(self):
        cases = (
            (PackageRuntimeObservation(), "PACKAGE_UPLOAD_REQUIRED"),
            (
                PackageRuntimeObservation(package_present=True, upload_in_progress=True),
                "PACKAGE_UPLOAD_IN_PROGRESS",
            ),
            (
                PackageRuntimeObservation(package_present=True, analyzing=True),
                "PACKAGE_ANALYZING",
            ),
            (
                PackageRuntimeObservation(
                    package_present=True,
                    validation="WARNING",
                    warning=RUNFULLTRUST_PACKAGE_WARNING,
                ),
                "DESKTOP_SELECTION_REQUIRED",
            ),
            (
                PackageRuntimeObservation(
                    package_present=True,
                    validation="WARNING",
                    warning=RUNFULLTRUST_PACKAGE_WARNING,
                    desktop_checked=True,
                ),
                "PACKAGE_SAVE_REQUIRED",
            ),
            (
                PackageRuntimeObservation(
                    package_present=True,
                    validation="WARNING",
                    warning=RUNFULLTRUST_PACKAGE_WARNING,
                    desktop_checked=True,
                    save_completed=True,
                ),
                "PACKAGE_RELOAD_REQUIRED",
            ),
            (
                PackageRuntimeObservation(
                    package_present=True,
                    validation="WARNING",
                    warning=RUNFULLTRUST_PACKAGE_WARNING,
                    desktop_checked=True,
                    save_completed=True,
                    retained_after_reload=True,
                ),
                "PACKAGE_SAVED",
            ),
        )
        for observation, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(package_next_action(observation), expected)

    def test_unknown_warning_and_error_fail_closed(self):
        self.assertEqual(
            package_next_action(
                PackageRuntimeObservation(
                    package_present=True,
                    validation="WARNING",
                    warning="Some new Microsoft warning",
                )
            ),
            "HOLD_UNKNOWN_MICROSOFT_RESPONSE",
        )
        self.assertEqual(
            package_next_action(
                PackageRuntimeObservation(
                    package_present=True,
                    validation="ERROR",
                    error="Package rejected",
                )
            ),
            "HOLD_PARTNER_CENTER_PACKAGE_VALIDATION",
        )

    def test_file_chooser_timeout_requires_reconciliation_before_retry(self):
        self.assertEqual(
            reconcile_file_chooser_timeout(package_present=False),
            "SAFE_RETRY_ALLOWED",
        )
        self.assertEqual(
            reconcile_file_chooser_timeout(package_present=True),
            "PACKAGE_RECONCILE_REQUIRED",
        )

    def test_session_expiry_prefers_product_overview_recovery(self):
        self.assertEqual(
            session_expiry_recovery_next_action(
                session_expired_dialog=True,
                product_breadcrumb_available=True,
                product_overview_visible=False,
                packages_complete=False,
            ),
            "NAVIGATE_PRODUCT_OVERVIEW",
        )
        self.assertEqual(
            session_expiry_recovery_next_action(
                session_expired_dialog=False,
                product_breadcrumb_available=False,
                product_overview_visible=True,
                packages_complete=True,
            ),
            "OVERVIEW_RECOVERED",
        )
        self.assertEqual(
            session_expiry_recovery_next_action(
                session_expired_dialog=True,
                product_breadcrumb_available=False,
                product_overview_visible=False,
                packages_complete=False,
            ),
            "HUMAN_SIGN_IN_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
