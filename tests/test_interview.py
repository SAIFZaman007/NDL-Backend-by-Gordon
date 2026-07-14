import unittest
import requests

BASE_URL = "http://localhost:8000/api"

class TestInterviewQuestionsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Admin login
        res = requests.post(f"{BASE_URL}/auth/login",
            json={"email": "admin@gordon.com", "password": "admin123"}
        )
        cls.token = res.json().get("token")
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_create_and_get_question(self):
        # Create
        data = {
            "topic": "CCNA",
            "questionText": "What is OSPF?",
            "correctAnswer": "Open Shortest Path First."
        }
        res = requests.post(f"{BASE_URL}/interviews/", json=data, headers=self.headers)
        self.assertEqual(res.status_code, 201)
        q_id = res.json()["id"]

        # Get
        res_get = requests.get(f"{BASE_URL}/interviews/")
        self.assertEqual(res_get.status_code, 200)
        self.assertTrue(any(q["id"] == q_id for q in res_get.json()))
        
        # Get by topic
        res_topic = requests.get(f"{BASE_URL}/interviews/topic/CCNA")
        self.assertEqual(res_topic.status_code, 200)
        self.assertTrue(len(res_topic.json()) > 0)

        # Delete
        res_del = requests.delete(f"{BASE_URL}/interviews/{q_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 204)

if __name__ == "__main__":
    unittest.main()
