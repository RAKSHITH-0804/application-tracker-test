import unittest
from datetime import datetime, timedelta, timezone
import jwt
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    JWT_SECRET
)

class TestAuthSecurity(unittest.TestCase):

    def test_password_hashing_and_verification(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)

        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))

    def test_jwt_access_token_lifecycle(self):
        user_id = 42
        token = create_access_token(user_id)
        decoded_id = decode_token(token, "access")
        self.assertEqual(user_id, decoded_id)

    def test_jwt_refresh_token_lifecycle(self):
        user_id = 42
        token = create_refresh_token(user_id)
        decoded_id = decode_token(token, "refresh")
        self.assertEqual(user_id, decoded_id)

    def test_token_type_mismatch_rejection(self):
        user_id = 42
        access_token = create_access_token(user_id)
        with self.assertRaises(Exception):
            decode_token(access_token, "refresh")

    def test_expired_token_rejection(self):
        payload = {
            "sub": "42",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
            "type": "access"
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        with self.assertRaises(Exception):
            decode_token(expired_token, "access")

if __name__ == "__main__":
    unittest.main()
