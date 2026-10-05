import unittest

from scripts.historical_verification_gate import validate_episode


class HistoricalVerificationGateTests(unittest.TestCase):
    def test_missing_bundle_fails_closed(self):
        errors = validate_episode({"title": "قصة", "narration": "نص"})
        self.assertTrue(any("HISTORICAL VERIFICATION REPORT" in error for error in errors))

    def test_rejected_report_cannot_pass(self):
        episode = {"historical_verification_report": {"decision": "REJECTED"}}
        errors = validate_episode(episode)
        self.assertTrue(errors)

    def test_unverified_low_confidence_claim_cannot_be_used(self):
        episode = {"historical_verification_report": {"decision": "APPROVED"}, "fact_table": [{"claim": "x", "source": "y", "confidence": "D", "verified": False, "decision": "use"}]}
        errors = validate_episode(episode)
        self.assertTrue(any("لا يجوز استخدام" in error for error in errors))

    def test_malformed_sources_returns_errors_instead_of_crashing(self):
        errors = validate_episode({"historical_verification_report": {"decision": "APPROVED", "sources": None}})
        self.assertTrue(errors)

    def test_unknown_confidence_and_unlisted_source_cannot_pass(self):
        errors = validate_episode({"historical_verification_report": {"decision": "APPROVED", "sources": []},
                                   "fact_table": [{"claim": "claim", "source": "invented", "confidence": "Z", "verified": True, "decision": "use"}]})
        self.assertTrue(any("درجة ثقة غير صالحة" in error for error in errors))
        self.assertTrue(any("المصدر غير موجود" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
