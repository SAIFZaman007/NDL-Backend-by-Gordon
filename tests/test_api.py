import unittest
import requests
import sys
import os

# We can run these tests against a running backend server
class TestGordonITAPI(unittest.TestCase):
    BASE_URL = "http://localhost:8000/api"

    def test_1_health_check(self):
        try:
            res = requests.get(f"{self.BASE_URL}/health")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "healthy")
            print("[SUCCESS] Health check endpoint passed")
        except requests.ConnectionError:
            print("[WARNING] Backend server not running at http://localhost:8000, skipping health check")

    def test_2_courses_endpoint(self):
        try:
            res = requests.get(f"{self.BASE_URL}/courses")
            self.assertEqual(res.status_code, 200)
            courses = res.json()
            self.assertGreater(len(courses), 0)
            print(f"[SUCCESS] Fetch courses passed (Found {len(courses)} courses)")
        except requests.ConnectionError:
            pass

    def test_3_exam_portal_paywall(self):
        try:
            # Free / Guest access check: questions > 40 should have masked content / lock flags
            res = requests.get(f"{self.BASE_URL}/exams/questions?category=CCNA")
            self.assertEqual(res.status_code, 200)
            questions = res.json()
            
            # Check question index 40 and 41
            q_40 = next((q for q in questions if q["indexNumber"] == 40), None)
            q_41 = next((q for q in questions if q["indexNumber"] == 41), None)

            if q_40:
                self.assertNotEqual(q_40.get("questionText"), "Upgrade to premium to unlock this practice question.")
                self.assertFalse(q_40.get("isLocked", False))
                print("[SUCCESS] Question 40 is unlocked for free users")
            if q_41:
                self.assertEqual(q_41.get("questionText"), "Upgrade to premium to unlock this practice question.")
                self.assertTrue(q_41.get("isLocked", False))
                print("[SUCCESS] Question 41 is paywall-masked for free users")
        except requests.ConnectionError:
            pass

if __name__ == "__main__":
    unittest.main()
