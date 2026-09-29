# Secure Share - Secure File Sharing System

**Secure Share** is a secure, authenticated, and encrypted file-sharing web application built for academic project submission and demonstration. It allows registered users to upload, encrypt, and share sensitive files with other registered users with granular security policies (expiration windows, download quotas, optional passphrases, and revocation controls).

---

## 🚀 Key Features

1. **User Authentication & Authorization**:
   - Registration, login, and session-based authentication using Flask sessions.
   - Passwords hashed using `werkzeug.security` (scrypt / PBKDF2 with salt) &mdash; never stored in plaintext.
   - Protected API and view routes requiring active authentication.

2. **Cryptographic Envelope Encryption**:
   - Implemented using the Python `cryptography` library (`Fernet` &mdash; AES-128 in CBC mode + HMAC-SHA256).
   - **Data Encryption Key (DEK)**: A unique 256-bit symmetric key is generated per file.
   - **Key Encryption Key (KEK / Master Key)**: The DEK is encrypted using the master key stored in `.env` and kept in `encryption_key_ref`.
   - Files are stored on disk with unpredictable UUIDv4 filenames (e.g., `4e2b8f...enc`). The original filename is never used on the filesystem.
   - Files are decrypted **on-the-fly in RAM** and streamed directly to the browser; plaintext is never written to disk during download.

3. **Granular Access Control & Security Policies**:
   - **Targeted Sharing**: Only the designated recipient (or sender) can download the file. Third parties receive `403 Forbidden`.
   - **Expiration Windows**: Shares can be configured to expire after 1 hour, 24 hours, 7 days, 30 days, or never.
   - **Download Quotas**: Supports one-time downloads (burn-after-reading) or download limits (1, 5, 10, etc.).
   - **Password-Protected Shares**: Senders can attach a secondary passphrase. Downloader must provide the passphrase prior to decryption.
   - **Access Revocation & Deletion**: Senders can instantly revoke active access or permanently delete shared files from disk.

4. **Audit Trail & Dashboard**:
   - Tracks audit logs for `REGISTER`, `LOGIN`, `UPLOAD`, `DOWNLOAD`, `REVOKE`, and `DELETE`.
   - Dashboard displays metrics: Files Sent, Files Received, Active Shares, Encrypted Storage Used, and Recent Activity feed.

5. **Modern Blue & Dark Theme Frontend**:
   - Pure vanilla HTML5, CSS3, and JavaScript (Fetch API & `XMLHttpRequest` upload progress).
   - Drag-and-drop file upload zone with real-time percentage upload progress bar.
   - Toast notification system, modal dialogs for password-protected files, and responsive tables.
   - **Zero external JS frameworks** (No React, Vue, Angular, or Node.js).

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JS | Clean responsive dark/blue theme, Fetch API, XMLHttpRequest |
| **Backend** | Python 3.10+, Flask 3.x | Lightweight, modular WSGI application |
| **Database** | SQLite via Flask-SQLAlchemy | Portable relational models; switchable to MySQL / PostgreSQL |
| **Cryptography** | `cryptography` (Fernet) | AES-128-CBC + HMAC-SHA256 envelope encryption |
| **Security** | Werkzeug Security, python-dotenv | Scrypt/PBKDF2 hashing, secure cookies, environment secrets |

---

## 📁 Project Structure

```text
secure-share/
├── app.py                  # Main Flask application and API route controllers
├── config.py               # Application configuration and security parameters
├── models.py               # SQLAlchemy ORM models (User, File, Share, ActivityLog)
├── crypto_utils.py         # Cryptographic engine: Fernet DEK/KEK envelope encryption
├── requirements.txt        # Python dependency manifest
├── .env                    # Environment secrets (SECRET_KEY, MASTER_ENCRYPTION_KEY, DATABASE_URL)
├── test_app.py             # Comprehensive automated test suite (9 security tests)
├── package_zip.py          # Script to generate clean project zip bundle
├── uploads/                # Directory storing encrypted file blobs (.enc)
├── static/
│   ├── css/
│   │   └── style.css       # Unified modern dark & blue theme stylesheet
│   └── js/
│       ├── main.js         # Toasts, modals, formatters, and logout logic
│       ├── auth.js         # Login and registration AJAX handlers
│       ├── dashboard.js    # Metric cards and recent activity log feed
│       ├── upload.js       # Drag-and-drop, recipient search, and progress bar
│       ├── sent.js         # Sent files table with revoke and delete actions
│       └── received.js     # Received files table with password modal & download trigger
└── templates/
    ├── base.html           # Base layout template with navbar and footer
    ├── index.html          # Public landing page with architecture explanation
    ├── login.html          # User login page
    ├── register.html       # User registration page
    ├── dashboard.html      # User analytics dashboard
    ├── upload.html         # File upload and encryption configuration page
    ├── sent.html           # Outgoing shares table
    └── received.html       # Incoming shares table and download modal
```

---

## ⚙️ Step-by-Step Installation & Setup

### 1. Prerequisites
Ensure you have **Python 3.10 or higher** installed on your system:
```bash
python --version
```

### 2. Create and Activate Virtual Environment (Recommended)
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Configuration (`.env`)
The project comes with a pre-configured `.env` file containing generated cryptographic keys.
To generate fresh keys if desired:
```bash
python -c "from cryptography.fernet import Fernet; import secrets; print('MASTER_ENCRYPTION_KEY=' + Fernet.generate_key().decode()); print('SECRET_KEY=' + secrets.token_hex(32))"
```

### 5. Run the Automated Tests
Verify all 9 security tests pass:
```bash
python -m unittest test_app.py
```

### 6. Run the Flask Server
```bash
python app.py
```
The server will start at: **`http://127.0.0.1:5000`**

### 7. Open in Browser
Open `http://127.0.0.1:5000` in your web browser.
- Click **Get Started** or **Create Free Account** to register a new user (e.g. `alice@example.com`).
- In an Incognito window or another browser, register a second user (e.g. `bob@example.com`).
- Upload a file from Alice's account and share it with Bob's email address.
- Log into Bob's account and click **Decrypt & Download** under Received Files.

---

## 🗄️ Database Schema

The database uses standard SQLAlchemy types designed to seamlessly switch between **SQLite** and **MySQL** (by changing `DATABASE_URL` in `.env` to `mysql+pymysql://user:password@host/dbname`).

### 1. `users` Table
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Unique user identifier |
| `name` | VARCHAR(100) | Full name of user |
| `email` | VARCHAR(120) UNIQUE | Email address used for login and recipient identification |
| `password_hash` | VARCHAR(256) | Salted hash generated via `generate_password_hash` |
| `created_at` | DATETIME | Account registration timestamp |

### 2. `files` Table
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Unique file record ID |
| `owner_id` | INTEGER (FK users.id) | ID of the user who uploaded the file |
| `original_name` | VARCHAR(255) | Original sanitized filename (e.g., `contract.pdf`) |
| `stored_name` | VARCHAR(64) UNIQUE | Unpredictable UUID filename on disk (e.g., `a1f8...enc`) |
| `file_size` | INTEGER | Original file size in bytes |
| `mime_type` | VARCHAR(100) | MIME type (e.g., `application/pdf`) |
| `encryption_key_ref`| TEXT | Data Encryption Key (DEK) encrypted with Master Key |
| `created_at` | DATETIME | Upload timestamp |

### 3. `shares` Table
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Unique share transaction ID |
| `file_id` | INTEGER (FK files.id) | Reference to uploaded file |
| `sender_id` | INTEGER (FK users.id) | User who shared the file |
| `receiver_id` | INTEGER (FK users.id) | Target recipient user |
| `share_password_hash`| VARCHAR(256) NULL | Hashed optional secondary file password |
| `expires_at` | DATETIME NULL | Expiration timestamp (null = never) |
| `max_downloads` | INTEGER NULL | Maximum download quota (e.g., 1 for self-destruct) |
| `download_count` | INTEGER | Number of successful downloads performed |
| `is_active` | BOOLEAN | Active flag (set to False when revoked by sender) |
| `created_at` | DATETIME | Share creation timestamp |

### 4. `activity_logs` Table
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Unique log ID |
| `user_id` | INTEGER (FK users.id) | User who performed or triggered the action |
| `file_id` | INTEGER NULL (FK files.id) | Associated file ID (if applicable) |
| `action` | VARCHAR(50) | Event type (`REGISTER`, `LOGIN`, `UPLOAD`, `DOWNLOAD`, `REVOKE`, `DELETE`) |
| `details` | VARCHAR(255) | Human-readable event description |
| `timestamp` | DATETIME | Event timestamp (UTC) |

---

## 🔒 Security Architecture (Detailed for Project Viva)

```text
[Plaintext File]
       │
       ▼
Generate random DEK (Fernet 32-byte key)
       │
       ├───► Encrypt File Bytes with DEK ───► Save as UUID.enc to disk (/uploads)
       │
       ▼
Encrypt DEK with MASTER_ENCRYPTION_KEY (.env)
       │
       ▼
Save Encrypted DEK to Database (files.encryption_key_ref)
```

### Why Envelope Encryption?
1. **Performance**: Encrypting with a symmetric key (Fernet / AES) is extremely fast and efficient for files of any size.
2. **Key Isolation**: Each file has a unique key. If an adversary compromises the key for one file, no other files in the system are compromised.
3. **Master Key Separation**: The master key is stored exclusively in `.env` (environment variable) and **never** written to the database. Even if the SQL database is leaked through a backup vulnerability, an attacker cannot decrypt the files without the server's `.env` master key.
4. **Zero Plaintext on Disk**: Files are decrypted strictly inside server RAM when authorized download occurs, and immediately streamed to the client HTTP connection.

---

## 🎓 Viva Questions & Answers (Exam Preparation)

### Q1: What is the main objective of this project?
> **Answer**: To provide a secure, authenticated, and audited peer-to-peer file sharing platform where files are encrypted at rest using symmetric envelope encryption (Fernet/AES-128), decoupling disk storage from plaintext filenames, and enforcing access rules like time-based expiration, download quotas, secondary password locks, and sender revocation.

### Q2: How does Fernet encryption work under the hood?
> **Answer**: Fernet is built upon standard cryptographic primitives provided by the Python `cryptography` library:
> - **AES-128 in CBC mode** with PKCS7 padding for confidentiality.
> - **HMAC with SHA-256** using a 128-bit key for integrity and authentication (prevents ciphertext tampering).
> - **Timestamp verification** to detect and reject replayed messages.
> - **Initialization Vector (IV)**: A cryptographically secure random 128-bit IV is generated for each encryption operation.

### Q3: What is Envelope Encryption and why did you use it?
> **Answer**: Envelope encryption is an industry standard (used by AWS KMS and Google Cloud KMS) where data is encrypted using a **Data Encryption Key (DEK)**, and the DEK itself is encrypted using a **Key Encryption Key (KEK / Master Key)**. 
> In our project:
> 1. A unique DEK is created for each file.
> 2. The master key encrypts the DEK.
> 3. The database stores only the encrypted DEK.
> This prevents a single compromised key from compromising all files and enables safe key management.

### Q4: How are passwords stored and why didn't you use MD5 or SHA-256 directly?
> **Answer**: Passwords are hashed using `werkzeug.security.generate_password_hash` which employs **scrypt** (or PBKDF2-HMAC-SHA256). 
> MD5 and standard SHA-256 are **unsalted and extremely fast**, making them vulnerable to Rainbow Table attacks and GPU-accelerated brute force. Werkzeug uses a cryptographically random salt and a computationally intensive work factor (key stretching) to resist brute-force attacks.

### Q5: How is SQL Injection prevented in this application?
> **Answer**: The application uses **Flask-SQLAlchemy (SQLAlchemy ORM)** which employs parameterized queries and prepared statements for all database interactions. User inputs are never concatenated directly into raw SQL strings, neutralizing SQL injection vectors.

### Q6: How does the application protect against Cross-Site Request Forgery (CSRF) and XSS?
> **Answer**:
> - Session cookies are configured with `SESSION_COOKIE_HTTPONLY = True`, preventing client-side JavaScript from accessing session tokens, mitigating session hijacking via Cross-Site Scripting (XSS).
> - `SESSION_COOKIE_SAMESITE = 'Lax'` prevents the browser from sending session cookies with cross-site requests, mitigating CSRF attacks.
> - Filenames are strictly sanitized using `werkzeug.utils.secure_filename` to prevent Directory Traversal / Path Traversal attacks (`../../etc/passwd`).

### Q7: Why are files saved with UUID names instead of their original filenames?
> **Answer**: 
> 1. **Path Traversal Prevention**: Malicious filenames containing `../` or special control characters cannot overwrite server files.
> 2. **Metadata Leakage Prevention**: If an attacker gains filesystem access to `/uploads`, they cannot deduce the file types, contents, or names since they are all named `<uuid4>.enc`.
> 3. **Filename Collision**: Users uploading files with identical names (e.g. `report.pdf`) will never overwrite each other.

### Q8: What prevents an unauthorized user from downloading someone else's file?
> **Answer**: In `/api/download/<share_id>`, the server checks the authenticated session `user_id`. It verifies that `current_user.id == share.receiver_id` or `current_user.id == share.sender_id`. If neither matches, it returns HTTP 403 Forbidden. Additionally, it verifies that the share is active, within its expiration window, and has not exceeded its download limit.

### Q9: How can this application be switched from SQLite to MySQL?
> **Answer**: Because we use Flask-SQLAlchemy with standard portable column definitions, switching to MySQL only requires:
> 1. Installing `pymysql` (`pip install pymysql`).
> 2. Changing the `DATABASE_URL` in `.env` to:
>    `mysql+pymysql://username:password@localhost:3306/secureshare`
> No changes to the application models or business logic are required.

### Q10: How does the "One-Time Download" feature work?
> **Answer**: When `max_downloads = 1`, the download route atomically checks `share.download_count < share.max_downloads`. After streaming the decrypted file, `share.download_count` is incremented to 1. Any subsequent attempt to download triggers `share.is_downloadable()`, which evaluates to `False` and returns HTTP 403.
