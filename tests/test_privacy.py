"""주민번호 이름표가 있는 오타 번호와 일반 주문번호를 구별한다. 모두 가상 값이다."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pkos_privacy import PrivacyFilter, Policy


class ResidentNumberPrivacy(unittest.TestCase):
    def test_labeled_invalid_date_is_masked(self):
        for label in ("주민등록번호", "주민번호", "주민 등록 번호", "주민\n등록\n번호"):
            for number in ("991350-1234567", "9913501234567", "991350 1234567"):
                with self.subTest(label=label, number=number):
                    masked, hits = PrivacyFilter().mask(f"{label}: {number}")
                    self.assertNotIn(number, masked)
                    self.assertEqual([h.kind for h in hits], ["주민등록번호"])
                    self.assertEqual(hits[0].confidence, "확실")

    def test_table_label_is_recognized(self):
        text = "| 주민등록번호 | 991350-1234567 |"
        masked, _ = PrivacyFilter().mask(text)
        self.assertEqual(masked, "| 주민등록번호 | ******-******* |")

    def test_unlabeled_invalid_date_order_number_is_preserved(self):
        for number in ("991350-1234567", "9913501234567"):
            text = f"주문번호: {number}"
            self.assertEqual(PrivacyFilter().mask(text), (text, []))

    def test_distant_label_does_not_match(self):
        text = "주민등록번호" + " " * 13 + "991350-1234567"
        self.assertEqual(PrivacyFilter().mask(text), (text, []))

    def test_valid_date_without_label_still_masked(self):
        masked, hits = PrivacyFilter().mask("900101-1234567")
        self.assertEqual(masked, "******-*******")
        self.assertEqual(hits[0].kind, "주민등록번호")

    def test_policy_is_respected(self):
        text = "주민번호: 991350-1234567"
        self.assertEqual(PrivacyFilter(Policy(주민등록번호="그대로")).mask(text), (text, []))
        self.assertEqual(PrivacyFilter(Policy(주민등록번호="삭제")).mask(text)[0], "주민번호: ")
        self.assertEqual(PrivacyFilter(Policy(주민등록번호="부분가림")).mask(text)[0], "주민번호: 991350-*******")

    def test_masking_is_idempotent(self):
        masked, _ = PrivacyFilter().mask("주민등록번호: 991350-1234567")
        self.assertEqual(PrivacyFilter().mask(masked), (masked, []))


if __name__ == "__main__":
    unittest.main()
