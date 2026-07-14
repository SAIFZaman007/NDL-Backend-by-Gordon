import unittest
import requests

BASE_URL = "http://localhost:8000/api"

class TestGordonBlogAPI(unittest.TestCase):
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
        requests.post(f"{BASE_URL}/auth/register", json={
            "email": "testbloguser@gordon.com",
            "password": "user123"
        })
        res2 = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "testbloguser@gordon.com",
            "password": "user123"
        })
        cls.user_token = res2.json()["access_token"]
        cls.user_headers = {"Authorization": f"Bearer {cls.user_token}"}

    def test_blog_crud_lifecycle(self):
        # 1. Create a draft post as admin
        payload = {
            "title": "Test CCNA Routing post",
            "excerpt": "This is a brief summary of CCNA routing post",
            "content": "Full markdown content of CCNA routing guide",
            "category": "CCNA",
            "coverImage": "https://example.com/cover.png",
            "readTime": "5 min read",
            "published": False
        }
        res = requests.post(f"{BASE_URL}/blog", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        post = res.json()
        self.assertIn("id", post)
        self.assertEqual(post["title"], "Test CCNA Routing post")
        self.assertEqual(post["published"], False)
        self.assertEqual(post["slug"], "test-ccna-routing-post")
        post_id = post["id"]
        slug = post["slug"]

        # 2. Regular user should not see draft post
        res_list = requests.get(f"{BASE_URL}/blog")
        self.assertEqual(res_list.status_code, 200)
        published_posts = res_list.json()
        self.assertFalse(any(p["id"] == post_id for p in published_posts))

        # 3. Regular user should not be able to retrieve draft post by slug
        res_get = requests.get(f"{BASE_URL}/blog/{slug}")
        self.assertEqual(res_get.status_code, 404)

        # 4. Non-admin should not list all posts via admin endpoint
        res_all = requests.get(f"{BASE_URL}/blog/admin/all", headers=self.user_headers)
        self.assertEqual(res_all.status_code, 403)

        # 5. Admin should see the post in admin list
        res_all_admin = requests.get(f"{BASE_URL}/blog/admin/all", headers=self.admin_headers)
        self.assertEqual(res_all_admin.status_code, 200)
        all_posts = res_all_admin.json()
        self.assertTrue(any(p["id"] == post_id for p in all_posts))

        # 6. Publish the post
        res_pub = requests.patch(f"{BASE_URL}/blog/{post_id}/publish", headers=self.admin_headers)
        self.assertEqual(res_pub.status_code, 200)
        self.assertEqual(res_pub.json()["published"], True)

        # 7. Public should now see it
        res_list = requests.get(f"{BASE_URL}/blog")
        self.assertEqual(res_list.status_code, 200)
        published_posts = res_list.json()
        self.assertTrue(any(p["id"] == post_id for p in published_posts))

        # 8. Retrieve by slug should succeed now
        res_get = requests.get(f"{BASE_URL}/blog/{slug}")
        self.assertEqual(res_get.status_code, 200)
        self.assertEqual(res_get.json()["id"], post_id)

        # 9. Update the post title
        update_payload = {"title": "Updated CCNA Routing Guide"}
        res_up = requests.put(f"{BASE_URL}/blog/{post_id}", json=update_payload, headers=self.admin_headers)
        self.assertEqual(res_up.status_code, 200)
        self.assertEqual(res_up.json()["title"], "Updated CCNA Routing Guide")
        self.assertEqual(res_up.json()["slug"], "updated-ccna-routing-guide")
        new_slug = res_up.json()["slug"]

        # 10. Check list categories
        res_cats = requests.get(f"{BASE_URL}/blog/categories")
        self.assertEqual(res_cats.status_code, 200)
        self.assertIn("CCNA", res_cats.json()["categories"])

        # 11. Delete the post
        res_del = requests.delete(f"{BASE_URL}/blog/{post_id}", headers=self.admin_headers)
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "deleted")

        # 12. Check deleted
        res_get_deleted = requests.get(f"{BASE_URL}/blog/{new_slug}")
        self.assertEqual(res_get_deleted.status_code, 404)

if __name__ == "__main__":
    unittest.main()
