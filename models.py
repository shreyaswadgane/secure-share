from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize SQLAlchemy instance
db = SQLAlchemy()


def utcnow():
    """Returns current UTC timestamp in a timezone-aware or standard naive UTC format."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """
    User Model
    Stores registered users with hashed passwords using Werkzeug security.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Relationships
    owned_files = db.relationship('File', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    sent_shares = db.relationship('Share', foreign_keys='Share.sender_id', backref='sender', lazy='dynamic')
    received_shares = db.relationship('Share', foreign_keys='Share.receiver_id', backref='receiver', lazy='dynamic')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy='dynamic')

    def set_password(self, password: str):
        """Hash and store user password using Werkzeug scrypt/pbkdf2."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify plain text password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Serialize user object to dictionary (excluding sensitive password hash)."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class File(db.Model):
    """
    File Model
    Tracks files uploaded to the server. Actual file contents are encrypted
    and stored on disk using the random stored_name (UUID).
    """
    __tablename__ = 'files'

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    file_size = db.Column(db.Integer, nullable=False)  # in bytes
    mime_type = db.Column(db.String(100), default='application/octet-stream')
    encryption_key_ref = db.Column(db.Text, nullable=False)  # Master-encrypted file DEK
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Relationships
    shares = db.relationship('Share', backref='file', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='file', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        """Serialize file metadata for API responses."""
        return {
            'id': self.id,
            'owner_id': self.owner_id,
            'original_name': self.original_name,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Share(db.Model):
    """
    Share Model
    Represents an access grant from a sender to a receiver for a specific file.
    Supports time expiry, download quotas, optional file passwords, and revocation.
    """
    __tablename__ = 'shares'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Optional file share password (hashed)
    share_password_hash = db.Column(db.String(256), nullable=True)

    # Expiration timestamp (None means never expires)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Download limit (None means unlimited)
    max_downloads = db.Column(db.Integer, nullable=True)
    download_count = db.Column(db.Integer, default=0, nullable=False)

    # Active status (Sender can toggle to revoke access instantly)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def set_password(self, password: str):
        """Set a password required to decrypt and download this shared file."""
        if password and password.strip():
            self.share_password_hash = generate_password_hash(password.strip())
        else:
            self.share_password_hash = None

    def check_password(self, password: str) -> bool:
        """Verify the password provided by downloader."""
        if not self.share_password_hash:
            return True
        if not password:
            return False
        return check_password_hash(self.share_password_hash, password)

    def is_expired(self) -> bool:
        """Check if share has passed its expiration time."""
        if self.expires_at is None:
            return False
        return utcnow() > self.expires_at

    def has_downloads_left(self) -> bool:
        """Check if download limit has been reached."""
        if self.max_downloads is None:
            return True
        return self.download_count < self.max_downloads

    def is_downloadable(self) -> tuple[bool, str]:
        """Validate if the file share is currently accessible for download."""
        if not self.is_active:
            return False, "This share has been revoked by the sender."
        if self.is_expired():
            return False, "This share link has expired."
        if not self.has_downloads_left():
            return False, "The maximum download limit for this file has been reached."
        return True, "OK"

    def to_dict(self):
        """Serialize share information for frontend tables."""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.name if self.sender else None,
            'sender_email': self.sender.email if self.sender else None,
            'receiver_id': self.receiver_id,
            'receiver_name': self.receiver.name if self.receiver else None,
            'receiver_email': self.receiver.email if self.receiver else None,
            'file_name': self.file.original_name if self.file else None,
            'file_size': self.file.file_size if self.file else 0,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'max_downloads': self.max_downloads,
            'download_count': self.download_count,
            'is_active': self.is_active,
            'is_expired': self.is_expired(),
            'has_password': self.share_password_hash is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ActivityLog(db.Model):
    """
    ActivityLog Model
    Maintains an audit trail of sensitive actions (upload, download, revoke, delete).
    """
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=True, index=True)
    action = db.Column(db.String(50), nullable=False)  # 'UPLOAD', 'DOWNLOAD', 'REVOKE', 'DELETE', etc.
    details = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=utcnow, nullable=False)

    def to_dict(self):
        """Serialize activity log entry."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'user_email': self.user.email if self.user else None,
            'file_id': self.file_id,
            'file_name': self.file.original_name if self.file else (self.details if self.details else '-'),
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
