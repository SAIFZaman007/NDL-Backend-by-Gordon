import unittest
import requests

BASE_URL = "http://localhost:8000/api"

class TestGordonAboutAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Admin login
        res = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "admin@gordon.com",
            "password": "admin123"
        })
        cls.admin_token = res.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Regular user login
        res2 = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "testbloguser@gordon.com",
            "password": "user123"
        })
        cls.user_token = res2.json()["access_token"]
        cls.user_headers = {"Authorization": f"Bearer {cls.user_token}"}

    def test_about_lifecycle(self):
        # 1. Fetch about content (public)
        res = requests.get(f"{BASE_URL}/about")
        self.assertEqual(res.status_code, 200)
        about_data = res.json()
        self.assertIn("title", about_data)
        self.assertIn("subTitle", about_data)
        self.assertIn("paragraphs", about_data)
        self.assertIn("stats", about_data)

        # 2. Try to update as non-admin (should be blocked)
        payload = {
            "title": "Hack Attack title",
            "subTitle": "Hacked",
            "paragraphs": ["We are anonymous"],
            "stats": [{"icon": "Award", "label": "Hackers", "sub": "Dark web"}]
        }
        res_hack = requests.post(f"{BASE_URL}/about", json=payload, headers=self.user_headers)
        self.assertEqual(res_hack.status_code, 403)

        # 3. Update as admin (should succeed)
        update_payload = {
            "title": "About Gordon Cisco Platform",
            "subTitle": "Our Identity",
            "paragraphs": [
                "Cisco certified instructor-led network training.",
                "Custom built dynamic exams."
            ],
            "stats": [
                {"icon": "Award", "label": "Cisco Gold Partner Certified", "sub": "Highest Level"}
            ]
        }
        res_up = requests.post(f"{BASE_URL}/about", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res_up.status_code, 200)
        updated_data = res_up.json()
        self.assertEqual(updated_data["title"], "About Gordon Cisco Platform")
        self.assertEqual(updated_data["subTitle"], "Our Identity")
        self.assertEqual(len(updated_data["paragraphs"]), 2)
        self.assertEqual(updated_data["stats"][0]["label"], "Cisco Gold Partner Certified")

        # 4. Fetch public again to verify updates persist
        res_check = requests.get(f"{BASE_URL}/about")
        self.assertEqual(res_check.status_code, 200)
        self.assertEqual(res_check.json()["title"], "About Gordon Cisco Platform")

if __name__ == "__main__":
    unittest.main()
