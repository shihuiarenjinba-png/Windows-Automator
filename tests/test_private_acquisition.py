import unittest

from store_manager.private_acquisition import (
    HOLD_CONFLICTING,
    HOLD_PAID_CHECKOUT,
    HOLD_PRIVATE_AUDIENCE,
    HOLD_ZERO_COST_ROUTE,
    PROMO_GENERATION_APPROVAL,
    STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED,
    TEMP_FREE_APPROVAL,
    ZERO_COST_FREE_TRIAL,
    ZERO_COST_PRIVATE_FREE,
    ZERO_COST_PROMO_EXISTING,
    PrivateAcquisitionObservation,
    classify_private_acquisition,
)


class PrivateAcquisitionTests(unittest.TestCase):
    def test_private_audience_must_be_proven(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=False,
                test_account_in_private_audience=True,
            )
        )
        self.assertEqual(decision.state, HOLD_PRIVATE_AUDIENCE)
        self.assertFalse(decision.acquisition_allowed_now)

    def test_signed_private_publish_is_required_before_acquisition(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=False,
            )
        )
        self.assertEqual(decision.state, STORE_SIGNED_PRIVATE_PUBLISH_REQUIRED)
        self.assertTrue(decision.write_required)
        self.assertTrue(decision.owner_approval_required)

    def test_existing_promo_code_is_preferred_zero_cost_route(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                existing_unredeemed_promo_code_available=True,
                free_trial_visible=True,
                free_trial_zero_cost_confirmed=True,
                current_price_is_free=True,
                paid_checkout_required=False,
            )
        )
        self.assertEqual(decision.state, ZERO_COST_PROMO_EXISTING)
        self.assertEqual(decision.acquisition_route, "promo_code_existing")
        self.assertTrue(decision.acquisition_allowed_now)
        self.assertFalse(decision.write_required)

    def test_zero_cost_trial_is_allowed_when_confirmed_live(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                free_trial_visible=True,
                free_trial_zero_cost_confirmed=True,
                paid_checkout_required=False,
            )
        )
        self.assertEqual(decision.state, ZERO_COST_FREE_TRIAL)
        self.assertEqual(decision.acquisition_route, "free_trial")
        self.assertTrue(decision.acquisition_allowed_now)

    def test_private_free_is_zero_cost(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                current_price_is_free=True,
                paid_checkout_required=False,
            )
        )
        self.assertEqual(decision.state, ZERO_COST_PRIVATE_FREE)
        self.assertEqual(decision.acquisition_route, "private_free")
        self.assertTrue(decision.acquisition_allowed_now)

    def test_promo_generation_requires_separate_approval(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                promo_code_generation_available=True,
            )
        )
        self.assertEqual(decision.state, PROMO_GENERATION_APPROVAL)
        self.assertTrue(decision.write_required)
        self.assertTrue(decision.owner_approval_required)
        self.assertFalse(decision.acquisition_allowed_now)

    def test_temporary_free_requires_separate_approval(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                temporary_free_change_available=True,
            )
        )
        self.assertEqual(decision.state, TEMP_FREE_APPROVAL)
        self.assertTrue(decision.write_required)
        self.assertTrue(decision.owner_approval_required)

    def test_paid_checkout_is_hold(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                paid_checkout_required=True,
            )
        )
        self.assertEqual(decision.state, HOLD_PAID_CHECKOUT)
        self.assertFalse(decision.acquisition_allowed_now)

    def test_conflicting_live_evidence_is_hold(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
                current_price_is_free=True,
                paid_checkout_required=True,
            )
        )
        self.assertEqual(decision.state, HOLD_CONFLICTING)

    def test_unknown_route_is_hold(self):
        decision = classify_private_acquisition(
            PrivateAcquisitionObservation(
                private_audience_configured=True,
                test_account_in_private_audience=True,
                store_signed_private_build_published=True,
            )
        )
        self.assertEqual(decision.state, HOLD_ZERO_COST_ROUTE)


if __name__ == "__main__":
    unittest.main()
