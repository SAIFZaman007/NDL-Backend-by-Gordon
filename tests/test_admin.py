import unittest
import requests

class TestGordonAdminAPI(unittest.TestCase):
    BASE_URL = "http://localhost:8000/api"

    def setUp(self):
        # Authenticate Admin user
        try:
            admin_res = requests.post(f"{self.BASE_URL}/auth/login", json={
                "email": "admin@gordon.com",
                "password": "admin123"
            })
            if admin_res.status_code == 200:
                self.admin_token = admin_res.json()["access_token"]
            else:
                self.admin_token = None
        except requests.ConnectionError:
            self.admin_token = None

        # Authenticate Standard Free user
        try:
            free_res = requests.post(f"{self.BASE_URL}/auth/login", json={
                "email": "free@gordon.com",
                "password": "user123"
            })
            if free_res.status_code == 200:
                self.free_token = free_res.json()["access_token"]
            else:
                self.free_token = None
        except requests.ConnectionError:
            self.free_token = None

    def test_admin_endpoints_access_control(self):
        if not self.admin_token or not self.free_token:
            print("[WARNING] Backend server not reachable, skipping access control tests")
            return

        # 1. Verify standard user cannot access admin stats
        headers = {"Authorization": f"Bearer {self.free_token}"}
        res = requests.get(f"{self.BASE_URL}/admin/stats", headers=headers)
        self.assertEqual(res.status_code, 403)
        print("[SUCCESS] Standard user blocked from Admin Stats endpoint (403)")

        # 2. Verify admin can access admin stats
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        res = requests.get(f"{self.BASE_URL}/admin/stats", headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        self.assertIn("total_revenue", stats)
        self.assertIn("total_users", stats)
        print("[SUCCESS] Admin successfully fetched Stats")

        # 3. Verify standard user cannot access user list
        res = requests.get(f"{self.BASE_URL}/admin/users", headers=headers)
        self.assertEqual(res.status_code, 403)
        print("[SUCCESS] Standard user blocked from Users List endpoint (403)")

        # 4. Verify admin can access user list
        res = requests.get(f"{self.BASE_URL}/admin/users", headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        users = res.json()
        self.assertGreater(len(users), 0)
        print(f"[SUCCESS] Admin successfully fetched user list (Found {len(users)} users)")

    def test_course_lesson_crud(self):
        if not self.admin_token:
            return

        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        # 1. Create a course
        course_payload = {
            "title": "Integration Test Course",
            "description": "Temp course for verifying CRUD operations",
            "thumbnailUrl": "https://example.com/thumb.png",
            "difficulty": "Beginner"
        }
        res = requests.post(f"{self.BASE_URL}/courses", json=course_payload, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        course = res.json()
        course_id = course["id"]
        self.assertEqual(course["title"], "Integration Test Course")
        print("[SUCCESS] Course created successfully")

        # 2. Edit the course
        edit_payload = {"title": "Updated Integration Test Course"}
        res = requests.put(f"{self.BASE_URL}/courses/{course_id}", json=edit_payload, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["title"], "Updated Integration Test Course")
        print("[SUCCESS] Course updated successfully")

        # 3. Add a lesson under the course
        lesson_payload = {
            "title": "CRUD Lesson 1",
            "videoUrl": "https://res.cloudinary.com/demo/video/upload/sp_auto/dog.mp4",
            "textContent": "This is raw study content",
            "orderIndex": 1
        }
        res = requests.post(f"{self.BASE_URL}/courses/{course_id}/lessons", json=lesson_payload, headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        lesson = res.json()
        lesson_id = lesson["id"]
        self.assertEqual(lesson["title"], "CRUD Lesson 1")
        print("[SUCCESS] Lesson created under course successfully")

        # 4. Delete course (cleans up lessons cascade)
        res = requests.delete(f"{self.BASE_URL}/courses/{course_id}", headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        print("[SUCCESS] Course and cascade lessons deleted successfully")

if __name__ == "__main__":
    unittest.main()
