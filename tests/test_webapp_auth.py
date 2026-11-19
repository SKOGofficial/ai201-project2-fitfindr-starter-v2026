import unittest
from unittest.mock import patch

import webapp


class AuthRouteTests(unittest.TestCase):
    def setUp(self):
        webapp.app.config["TESTING"] = True
        self.client = webapp.app.test_client()

    def test_login_page_offers_sign_in_and_account_creation(self):
        response = self.client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back", response.data)
        self.assertIn(b"Create an account", response.data)

    def test_login_rejects_missing_credentials(self):
        with patch("webapp.db.sign_in") as sign_in:
            response = self.client.post(
                "/login",
                data={"email": "", "password": ""},
                follow_redirects=True,
            )

        self.assertIn(b"Enter your email and password.", response.data)
        sign_in.assert_not_called()

    def test_signup_rejects_short_password(self):
        with patch("webapp.db.sign_up") as sign_up:
            response = self.client.post(
                "/signup",
                data={"email": "new@example.com", "password": "123"},
                follow_redirects=True,
            )

        self.assertIn(b"at least 6 characters", response.data)
        sign_up.assert_not_called()

    def test_signup_logs_in_when_confirmation_is_not_required(self):
        user_id = "11111111-1111-4111-8111-111111111111"
        with patch(
            "webapp.db.sign_up",
            return_value={"user_id": user_id, "needs_confirmation": False},
        ), patch("webapp.db.list_wardrobe_items", return_value=[]):
            response = self.client.post(
                "/signup",
                data={"email": "new@example.com", "password": "123456"},
            )
            member_home = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(b"Wardrobe", member_home.data)

    def test_login_and_logout_gate_account_pages(self):
        user_id = "11111111-1111-4111-8111-111111111111"
        with patch("webapp.db.sign_in", return_value=user_id):
            response = self.client.post(
                "/login",
                data={"email": "user@example.com", "password": "123456"},
            )

        self.assertEqual(response.status_code, 302)
        with patch("webapp.db.list_search_history", return_value=[]):
            self.assertEqual(self.client.get("/history").status_code, 200)

        self.client.post("/logout")
        self.assertEqual(self.client.get("/history").status_code, 302)


if __name__ == "__main__":
    unittest.main()
