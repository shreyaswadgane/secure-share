import os
from dotenv import load_dotenv

# Base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    """
    Application Configuration Class
    Manages security keys, database connections, upload policies, and session flags.
    Can be easily extended for Production, Testing, or MySQL deployment.
    """
    # Secret key for Flask session cookie signing and CSRF tokens
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-insecure-dev-key-change-me')

    # Fernet master key for envelope encryption of file data keys
    MASTER_ENCRYPTION_KEY = os.getenv('MASTER_ENCRYPTION_KEY')

    # Database connection URI
    # Default is SQLite. To switch to MySQL, update DATABASE_URL in .env:
    # mysql+pymysql://<user>:<password>@<host>:<port>/<database>
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(basedir, 'secureshare.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Maximum file upload limit: 25 Megabytes (25 * 1024 * 1024 bytes)
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    # Storage folder for encrypted file blobs on the filesystem
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')

    # Allowed safe file extensions (rejects dangerous executable files like .exe, .bat, .sh, .msi, etc.)
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'docx', 'doc', 'txt', 'rtf', 'odt', 'csv', 'xlsx', 'xls', 'pptx', 'ppt', 'md',
        # Images
        'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico',
        # Archives
        'zip', 'tar', 'gz', '7z', 'rar',
        # Media
        'mp3', 'wav', 'ogg', 'mp4', 'mkv', 'avi', 'webm',
        # Structured Data & Code (text/safe formats)
        'json', 'xml', 'yaml', 'yml', 'sql', 'py', 'c', 'cpp', 'java', 'html', 'css', 'js'
    }

    # Session cookie security settings
    # Prevents client-side scripts from reading session cookies (XSS defense)
    SESSION_COOKIE_HTTPONLY = True
    # Prevents CSRF attacks via cross-site requests
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Set to True when running under HTTPS in production
    SESSION_COOKIE_SECURE = False

    @staticmethod
    def init_app(app):
        """Ensure critical directories exist on application startup."""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
