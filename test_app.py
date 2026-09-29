"""
Comprehensive Automated Test Suite for Secure Share System
Tests:
- Authentication & Password Hashing (Werkzeug)
- Cryptographic Envelope Encryption & Decryption
- Access Control & Authorization (Sender, Receiver, Third-Party)
- Download Limits (One-Time Downloads)
- Expiration Window Enforcement
- Password Protected Shares
- Share Revocation
- Activity Logging & Dashboard Aggregation
"""

import os
import io
import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from config import Config
from app import app
from models import db, User, File, Share, ActivityLog, utcnow
from crypto_utils import decrypt_stored_file


class SecureShareTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test_uploads')
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

        # Clean up test upload files
        upload_folder = app.config['UPLOAD_FOLDER']
        if os.path.exists(upload_folder):
            for fname in os.listdir(upload_folder):
                try:
                    os.remove(os.path.join(upload_folder, fname))
                except OSError:
                    pass
            try:
                os.rmdir(upload_folder)
            except OSError:
                pass

    def register_user(self, name, email, password):
        return self.client.post('/api/register', json={
            'name': name,
            'email': email,
            'password': password
        })

    def login_user(self, email, password):
        return self.client.post('/api/login', json={
            'email': email,
            'password': password
        })

    def logout_user(self):
        return self.client.post('/api/logout')

    def test_user_registration_and_password_hashing(self):
        """Verify user registration, uniqueness check, and Werkzeug password hashing."""
        res = self.register_user('Alice', 'alice@test.com', 'Secret123!')
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])

        # Verify password is not stored in plaintext in the database
        user = User.query.filter_by(email='alice@test.com').first()
        self.assertIsNotNone(user)
        self.assertNotEqual(user.password_hash, 'Secret123!')
        self.assertTrue(user.check_password('Secret123!'))
        self.assertFalse(user.check_password('WrongPassword'))

        # Verify duplicate registration fails with 409
        dup_res = self.register_user('Alice Two', 'alice@test.com', 'Secret123!')
        self.assertEqual(dup_res.status_code, 409)

    def test_user_login_and_session(self):
        """Verify login validation and session initialization."""
        self.register_user('Bob', 'bob@test.com', 'BobPassword123')
        self.logout_user()

        # Invalid password
        fail_res = self.login_user('bob@test.com', 'BadPassword')
        self.assertEqual(fail_res.status_code, 401)

        # Correct password
        success_res = self.login_user('bob@test.com', 'BobPassword123')
        self.assertEqual(success_res.status_code, 200)

        # Check /api/me
        me_res = self.client.get('/api/me')
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(me_res.get_json()['logged_in'])

    def test_file_upload_envelope_encryption_and_decryption(self):
        """Verify that uploaded files are encrypted on disk and decrypted on-the-fly."""
        # 1. Register Alice and Bob
        self.register_user('Alice', 'alice@test.com', 'AlicePassword123')
        self.register_user('Bob', 'bob@test.com', 'BobPassword123')

        # Login as Alice
        self.login_user('alice@test.com', 'AlicePassword123')

        # Upload a confidential text file shared with Bob
        raw_content = b"Confidential Research Paper: Quantum Cryptography and Zero-Knowledge Proofs."
        original_hash = hashlib.sha256(raw_content).hexdigest()

        upload_data = {
            'file': (io.BytesIO(raw_content), 'research.txt'),
            'recipient': 'bob@test.com',
            'expiry': '24h',
            'max_downloads': 'unlimited'
        }

        up_res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        self.assertEqual(up_res.status_code, 201)
        up_json = up_res.get_json()
        share_id = up_json['share_id']

        # 2. Verify stored file on disk is encrypted (NOT plaintext)
        file_rec = File.query.first()
        self.assertIsNotNone(file_rec)
        disk_path = os.path.join(app.config['UPLOAD_FOLDER'], file_rec.stored_name)
        self.assertTrue(os.path.exists(disk_path))

        with open(disk_path, 'rb') as f:
            disk_ciphertext = f.read()

        # Ciphertext must NOT contain raw content
        self.assertNotIn(raw_content, disk_ciphertext)

        # 3. Log in as Bob (recipient) and download decrypted file
        self.logout_user()
        self.login_user('bob@test.com', 'BobPassword123')

        dl_res = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl_res.status_code, 200)
        decrypted_content = dl_res.data

        # Verify decrypted content matches original byte-for-byte
        self.assertEqual(decrypted_content, raw_content)
        self.assertEqual(hashlib.sha256(decrypted_content).hexdigest(), original_hash)

    def test_unauthorized_access_prevented(self):
        """Verify that a third user cannot download a share meant for someone else."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')
        self.register_user('Eve', 'eve@test.com', 'Pass123')

        # Alice shares with Bob
        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Secret for Bob only"), 'bob_secret.txt'),
            'recipient': 'bob@test.com'
        }
        res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = res.get_json()['share_id']

        # Eve attempts to download
        self.logout_user()
        self.login_user('eve@test.com', 'Pass123')

        dl_res = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl_res.status_code, 403)
        self.assertIn('permission', dl_res.get_json()['error'].lower())

    def test_download_quota_one_time_download(self):
        """Verify that a one-time download quota blocks subsequent downloads."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')

        # Alice shares file with 1-time limit
        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Burn after reading content"), 'self_destruct.txt'),
            'recipient': 'bob@test.com',
            'max_downloads': '1'
        }
        res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = res.get_json()['share_id']

        # Bob downloads first time -> success
        self.logout_user()
        self.login_user('bob@test.com', 'Pass123')

        dl1 = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl1.status_code, 200)

        # Bob downloads second time -> blocked!
        dl2 = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl2.status_code, 403)
        self.assertIn('limit', dl2.get_json()['error'].lower())

    def test_expired_share_blocked(self):
        """Verify that expired share links cannot be downloaded."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')

        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Time sensitive file"), 'time.txt'),
            'recipient': 'bob@test.com'
        }
        res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = res.get_json()['share_id']

        # Artificially set share to expired
        share = db.session.get(Share, share_id)
        share.expires_at = utcnow() - timedelta(minutes=10)
        db.session.commit()

        # Bob attempts download -> blocked by expiration
        self.logout_user()
        self.login_user('bob@test.com', 'Pass123')

        dl_res = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl_res.status_code, 403)
        self.assertIn('expired', dl_res.get_json()['error'].lower())

    def test_password_protected_share(self):
        """Verify that shares with passwords require the correct passphrase."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')

        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Encrypted top secret"), 'secret.txt'),
            'recipient': 'bob@test.com',
            'password': 'SharePassphrase456'
        }
        res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = res.get_json()['share_id']

        self.logout_user()
        self.login_user('bob@test.com', 'Pass123')

        # 1. Download without password -> 403
        no_pw = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(no_pw.status_code, 403)
        self.assertTrue(no_pw.get_json().get('requires_password'))

        # 2. Download with wrong password -> 403
        wrong_pw = self.client.post(f'/api/download/{share_id}', json={'password': 'WrongPassword!'})
        self.assertEqual(wrong_pw.status_code, 403)

        # 3. Download with correct password -> 200
        correct_pw = self.client.post(f'/api/download/{share_id}', json={'password': 'SharePassphrase456'})
        self.assertEqual(correct_pw.status_code, 200)
        self.assertEqual(correct_pw.data, b"Encrypted top secret")

    def test_revoke_share(self):
        """Verify that the sender can revoke access to an active share."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')

        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Data before revocation"), 'doc.txt'),
            'recipient': 'bob@test.com'
        }
        res = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = res.get_json()['share_id']

        # Alice revokes the share
        revoke_res = self.client.delete(f'/api/share/{share_id}?action=revoke')
        self.assertEqual(revoke_res.status_code, 200)

        # Bob attempts download -> blocked because share is revoked
        self.logout_user()
        self.login_user('bob@test.com', 'Pass123')

        dl_res = self.client.get(f'/api/download/{share_id}')
        self.assertEqual(dl_res.status_code, 403)
        self.assertIn('revoked', dl_res.get_json()['error'].lower())

    def test_activity_logging_and_dashboard_stats(self):
        """Verify audit logs are recorded and dashboard metrics aggregate accurately."""
        self.register_user('Alice', 'alice@test.com', 'Pass123')
        self.register_user('Bob', 'bob@test.com', 'Pass123')

        self.login_user('alice@test.com', 'Pass123')
        upload_data = {
            'file': (io.BytesIO(b"Important presentation"), 'slides.txt'),
            'recipient': 'bob@test.com'
        }
        up = self.client.post('/api/upload', data=upload_data, content_type='multipart/form-data')
        share_id = up.get_json()['share_id']

        # Bob logs in and downloads
        self.logout_user()
        self.login_user('bob@test.com', 'Pass123')
        self.client.get(f'/api/download/{share_id}')

        # Fetch Bob's dashboard
        dash_res = self.client.get('/api/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        data = dash_res.get_json()

        self.assertTrue(data['success'])
        self.assertEqual(data['stats']['total_received'], 1)
        self.assertEqual(data['stats']['total_sent'], 0)

        # Check activity logs exist
        logs = ActivityLog.query.all()
        actions = [log.action for log in logs]
        self.assertIn('REGISTER', actions)
        self.assertIn('UPLOAD', actions)
        self.assertIn('DOWNLOAD', actions)


if __name__ == '__main__':
    unittest.main()
