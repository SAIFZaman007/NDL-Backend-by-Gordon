import unittest
import requests

BASE_URL = "http://localhost:8000/api"

class TestGordonSubscriptionsAPI(unittest.TestCase):
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

    def test_subscriptions_crud_lifecycle(self):
        # 1. Fetch public subscriptions (should get fallback defaults)
        res = requests.get(f"{BASE_URL}/subscriptions")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 3)

        # 2. Block non-admin from creating subscription plan
        payload = {
            "name": "Super Hacker Plan",
            "planType": "monthly",
            "price": 99.99,
            "billingPeriod": "month",
            "description": "Exclusive hacking content",
            "features": ["1", "2"],
            "badge": "LIT",
            "cta": "Hack Now",
            "featured": True
        }
        res_hack = requests.post(f"{BASE_URL}/subscriptions", json=payload, headers=self.user_headers)
        self.assertEqual(res_hack.status_code, 403)

        # 3. Admin creates plan successfully
        res_create = requests.post(f"{BASE_URL}/subscriptions", json=payload, headers=self.admin_headers)
        self.assertEqual(res_create.status_code, 200)
        plan = res_create.json()
        self.assertIn("id", plan)
        self.assertEqual(plan["name"], "Super Hacker Plan")
        plan_id = plan["id"]

        # 4. Fetch public (should get list containing the new plan)
        res_list = requests.get(f"{BASE_URL}/subscriptions")
        self.assertEqual(res_list.status_code, 200)
        self.assertTrue(any(p["id"] == plan_id for p in res_list.json()))

        # 5. Update plan as admin
        update_payload = {
            "name": "Super CCNA Premium",
            "price": 25.00
        }
        res_up = requests.put(f"{BASE_URL}/subscriptions/{plan_id}", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(res_up.json()["name"], "Super CCNA Premium")
        self.assertEqual(res_up.json()["price"], 25.00)

        # 6. Delete plan as admin
        res_del = requests.delete(f"{BASE_URL}/subscriptions/{plan_id}", headers=self.admin_headers)
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "deleted")

        # 7. Check deleted
        res_list_after = requests.get(f"{BASE_URL}/subscriptions")
        self.assertEqual(res_list_after.status_code, 200)
        self.assertFalse(any(p["id"] == plan_id for p in res_list_after.json()))

if __name__ == "__main__":
    unittest.main()
