import unittest
import requests

BASE_URL = "http://localhost:8000/api"

class TestGordonTestimonialsAPI(unittest.TestCase):
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

    def test_testimonials_crud_lifecycle(self):
        # 1. Fetch public testimonials (should return fallback defaults)
        res = requests.get(f"{BASE_URL}/testimonials")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 3)

        # 2. Block non-admin from creating a testimonial
        payload = {
            "name": "Bruce Wayne",
            "role": "Security Engineer",
            "company": "Wayne Enterprises",
            "rating": 5,
            "text": "CCNA routing guide by Gordon helped me protect Gotham networks!"
        }
        res_hack = requests.post(f"{BASE_URL}/testimonials", json=payload, headers=self.user_headers)
        self.assertEqual(res_hack.status_code, 403)

        # 3. Admin creates testimonial successfully
        res_create = requests.post(f"{BASE_URL}/testimonials", json=payload, headers=self.admin_headers)
        self.assertEqual(res_create.status_code, 200)
        review = res_create.json()
        self.assertIn("id", review)
        self.assertEqual(review["name"], "Bruce Wayne")
        review_id = review["id"]

        # 4. Fetch public (should get list containing the new review)
        res_list = requests.get(f"{BASE_URL}/testimonials")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(p["id"] == review_id for p in res_list.json()))

        # 5. Update review as admin
        update_payload = {
            "name": "Batman",
            "rating": 5
        }
        res_up = requests.put(f"{BASE_URL}/testimonials/{review_id}", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(res_up.json()["name"], "Batman")

        # 6. Delete review as admin
        res_del = requests.delete(f"{BASE_URL}/testimonials/{review_id}", headers=self.admin_headers)
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "deleted")

        # 7. Check deleted
        res_list_after = requests.get(f"{BASE_URL}/testimonials")
        self.assertEqual(res_list_after.status_code, 200)
        self.assertFalse(any(p["id"] == review_id for p in res_list_after.json()))

if __name__ == "__main__":
    unittest.main()
