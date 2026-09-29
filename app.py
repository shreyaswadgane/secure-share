import os
import io
import re
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for, send_file, abort
)
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, File, Share, ActivityLog, utcnow
from crypto_utils import (
    allowed_file, encrypt_and_store_file,
    decrypt_stored_file, delete_stored_file
)

# Initialize Flask application
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database and directories
db.init_app(app)
Config.init_app(app)

# Ensure database tables exist within application context
with app.app_context():
    db.create_all()


# -----------------------------------------------------------------------------
# Authentication & Authorization Helpers
# -----------------------------------------------------------------------------

def get_current_user():
    """Retrieve currently authenticated user from session, or None."""
    user_id = session.get('user_id')
    if user_id:
        return db.session.get(User, user_id)
    return None


def login_required(f):
    """Decorator to protect JSON API routes. Returns 401 if unauthorized."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not get_current_user():
            return jsonify({'success': False, 'error': 'Authentication required. Please log in.'}), 401
        return f(*args, **kwargs)
    return decorated_function


def page_login_required(f):
    """Decorator to protect HTML view routes. Redirects to login page if unauthorized."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not get_current_user():
            return redirect(url_for('login_page', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def log_activity(user_id: int, action: str, details: str = None, file_id: int = None):
    """Helper function to record an audit trail event in the activity_logs table."""
    try:
        log_entry = ActivityLog(
            user_id=user_id,
            file_id=file_id,
            action=action,
            details=details,
            timestamp=utcnow()
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to record activity log: {e}")


# -----------------------------------------------------------------------------
# Frontend Page Routes (HTML)
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """Landing page with project introduction and features overview."""
    user = get_current_user()
    return render_template('index.html', user=user)


@app.route('/login')
def login_page():
    """User login page."""
    if get_current_user():
        return redirect(url_for('dashboard_page'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    """User registration page."""
    if get_current_user():
        return redirect(url_for('dashboard_page'))
    return render_template('register.html')


@app.route('/dashboard')
@page_login_required
def dashboard_page():
    """User dashboard showing summary statistics and recent activity."""
    user = get_current_user()
    return render_template('dashboard.html', user=user)


@app.route('/upload')
@page_login_required
def upload_page():
    """Upload & Encrypt file page with security settings."""
    user = get_current_user()
    return render_template('upload.html', user=user)


@app.route('/sent')
@page_login_required
def sent_page():
    """Sent files overview page with revoke/delete controls."""
    user = get_current_user()
    return render_template('sent.html', user=user)


@app.route('/received')
@page_login_required
def received_page():
    """Received files page where recipient can download decrypted files."""
    user = get_current_user()
    return render_template('received.html', user=user)


# -----------------------------------------------------------------------------
# Authentication API Routes
# -----------------------------------------------------------------------------

@app.route('/api/register', methods=['POST'])
def api_register():
    """
    Register a new user account.
    Validates input fields, checks email uniqueness, and securely hashes password.
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    # Input Validation
    if not name or len(name) < 2:
        return jsonify({'success': False, 'error': 'Name must be at least 2 characters long.'}), 400

    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not email or not re.match(email_regex, email):
        return jsonify({'success': False, 'error': 'Please provide a valid email address.'}), 400

    if not password or len(password) < 6:
        return jsonify({'success': False, 'error': 'Password must be at least 6 characters long.'}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'An account with this email already exists.'}), 409

    # Create user
    try:
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Log in the user immediately
        session['user_id'] = user.id
        log_activity(user.id, 'REGISTER', f'New account registered: {user.email}')

        return jsonify({
            'success': True,
            'message': 'Registration successful! Welcome to Secure Share.',
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Registration failed: {str(e)}'}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    """
    Authenticate user credentials and initiate session.
    """
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'success': False, 'error': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'error': 'Invalid email or password.'}), 401

    session['user_id'] = user.id
    log_activity(user.id, 'LOGIN', f'User logged in: {user.email}')

    return jsonify({
        'success': True,
        'message': 'Login successful.',
        'user': user.to_dict()
    })


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """
    Terminate user session.
    """
    user = get_current_user()
    if user:
        log_activity(user.id, 'LOGOUT', f'User logged out: {user.email}')
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})


@app.route('/api/me')
def api_me():
    """
    Check current authentication status and retrieve user profile.
    """
    user = get_current_user()
    if user:
        return jsonify({'logged_in': True, 'user': user.to_dict()})
    return jsonify({'logged_in': False, 'user': None})


@app.route('/api/users/search')
@login_required
def api_search_users():
    """
    Autocomplete/search helper to find recipients by email or name.
    Excludes the currently logged-in user.
    """
    query = request.args.get('q', '').strip()
    current_user = get_current_user()
    if not query or len(query) < 2:
        return jsonify({'users': []})

    users = User.query.filter(
        (User.email.ilike(f'%{query}%')) | (User.name.ilike(f'%{query}%')),
        User.id != current_user.id
    ).limit(8).all()

    return jsonify({'users': [u.to_dict() for u in users]})


# -----------------------------------------------------------------------------
# File Upload & Encryption API Routes
# -----------------------------------------------------------------------------

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload():
    """
    Upload and encrypt a file for a specific recipient.
    Features:
    - Encrypts file using Fernet/AES before writing to disk
    - Stored under a random UUID (original filename never touches disk)
    - Validates recipient email or username
    - Configures optional expiration time, download limits, and share password
    """
    current_user = get_current_user()

    # 1. Validate file presence
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part in the request.'}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400

    original_filename = secure_filename(file.filename)
    if not original_filename:
        original_filename = "unnamed_file"

    if not allowed_file(original_filename):
        return jsonify({
            'success': False,
            'error': f'File type not allowed. Allowed types: {", ".join(sorted(list(Config.ALLOWED_EXTENSIONS)[:15]))}...'
        }), 400

    # 2. Validate recipient
    recipient_identifier = request.form.get('recipient', '').strip().lower()
    if not recipient_identifier:
        return jsonify({'success': False, 'error': 'Recipient email or username is required.'}), 400

    recipient = User.query.filter(
        (User.email == recipient_identifier) | (User.name.ilike(recipient_identifier))
    ).first()

    if not recipient:
        return jsonify({'success': False, 'error': f'Recipient "{recipient_identifier}" was not found.'}), 404

    if recipient.id == current_user.id:
        return jsonify({'success': False, 'error': 'You cannot share files with yourself.'}), 400

    # 3. Read file data and check size
    file_bytes = file.read()
    if len(file_bytes) == 0:
        return jsonify({'success': False, 'error': 'Uploaded file is empty.'}), 400

    if len(file_bytes) > Config.MAX_CONTENT_LENGTH:
        return jsonify({'success': False, 'error': 'File exceeds maximum size limit of 25MB.'}), 413

    # 4. Security settings (Expiry, Download limits, Password)
    expiry_option = request.form.get('expiry', 'never')
    expires_at = None
    now = utcnow()

    if expiry_option == '1h':
        expires_at = now + timedelta(hours=1)
    elif expiry_option == '24h':
        expires_at = now + timedelta(hours=24)
    elif expiry_option == '7d':
        expires_at = now + timedelta(days=7)
    elif expiry_option == '30d':
        expires_at = now + timedelta(days=30)

    download_limit_val = request.form.get('max_downloads', 'unlimited')
    max_downloads = None
    if download_limit_val in ['1', '5', '10', '20']:
        max_downloads = int(download_limit_val)

    share_password = request.form.get('password', '').strip()

    # 5. Encrypt file and store on disk
    try:
        stored_name, encrypted_dek, file_size = encrypt_and_store_file(
            file_bytes=file_bytes,
            upload_folder=app.config['UPLOAD_FOLDER']
        )

        # 6. Save File record in database
        file_record = File(
            owner_id=current_user.id,
            original_name=original_filename,
            stored_name=stored_name,
            file_size=file_size,
            mime_type=file.mimetype or 'application/octet-stream',
            encryption_key_ref=encrypted_dek
        )
        db.session.add(file_record)
        db.session.flush()  # Flush to generate file_record.id

        # 7. Create Share record
        share = Share(
            file_id=file_record.id,
            sender_id=current_user.id,
            receiver_id=recipient.id,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
            is_active=True
        )
        if share_password:
            share.set_password(share_password)

        db.session.add(share)
        db.session.commit()

        # 8. Record Activity
        log_activity(
            user_id=current_user.id,
            file_id=file_record.id,
            action='UPLOAD',
            details=f"Shared '{original_filename}' with {recipient.email}"
        )

        return jsonify({
            'success': True,
            'message': f"File '{original_filename}' encrypted and shared with {recipient.name} successfully!",
            'share_id': share.id
        }), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error during file upload and encryption: {e}")
        return jsonify({'success': False, 'error': f'Failed to encrypt and store file: {str(e)}'}), 500


# -----------------------------------------------------------------------------
# Sent & Received Files API Routes
# -----------------------------------------------------------------------------

@app.route('/api/files/sent')
@login_required
def api_sent_files():
    """
    Retrieve all files shared by the current user.
    """
    current_user = get_current_user()
    shares = Share.query.filter_by(sender_id=current_user.id).order_by(Share.created_at.desc()).all()
    return jsonify({
        'success': True,
        'shares': [s.to_dict() for s in shares]
    })


@app.route('/api/files/received')
@login_required
def api_received_files():
    """
    Retrieve all files shared with the current user.
    """
    current_user = get_current_user()
    shares = Share.query.filter_by(receiver_id=current_user.id).order_by(Share.created_at.desc()).all()
    return jsonify({
        'success': True,
        'shares': [s.to_dict() for s in shares]
    })


# -----------------------------------------------------------------------------
# File Download & Decryption Route
# -----------------------------------------------------------------------------

@app.route('/api/download/<int:share_id>', methods=['GET', 'POST'])
@login_required
def api_download(share_id: int):
    """
    Decrypts the file on-the-fly in memory and streams it to authorized recipient.
    Enforces:
    - User is the recipient (or the original sender)
    - Share is active
    - Expiration time has not passed
    - Download limit has not been exceeded
    - Optional share password check
    - Increments download counter
    - Logs download event in activity_logs
    """
    current_user = get_current_user()
    share = db.session.get(Share, share_id)

    if not share:
        return jsonify({'success': False, 'error': 'Share link not found.'}), 404

    # Permission check: must be recipient or sender
    if current_user.id != share.receiver_id and current_user.id != share.sender_id:
        return jsonify({'success': False, 'error': 'You do not have permission to access this file.'}), 403

    # If downloader is the recipient, enforce share restrictions
    if current_user.id == share.receiver_id:
        can_download, reason = share.is_downloadable()
        if not can_download:
            return jsonify({'success': False, 'error': reason}), 403

    # Check share password protection
    if share.share_password_hash:
        provided_password = ''
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            provided_password = data.get('password') or request.form.get('password') or ''
        else:
            provided_password = request.args.get('password', '')

        # Check request header fallback
        if not provided_password:
            provided_password = request.headers.get('X-Share-Password', '')

        if not share.check_password(provided_password):
            return jsonify({
                'success': False,
                'requires_password': True,
                'error': 'This file is protected by a password. Please enter the correct password.'
            }), 403

    # Read and decrypt file on-the-fly
    file_record = share.file
    try:
        decrypted_bytes = decrypt_stored_file(
            stored_name=file_record.stored_name,
            encrypted_dek_str=file_record.encryption_key_ref,
            upload_folder=app.config['UPLOAD_FOLDER']
        )
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'Encrypted file not found on disk.'}), 404
    except Exception as e:
        app.logger.error(f"Decryption error for share {share_id}: {e}")
        return jsonify({'success': False, 'error': 'Failed to decrypt file. Key mismatch or corrupted data.'}), 500

    # Increment download counter if downloaded by recipient
    if current_user.id == share.receiver_id:
        share.download_count += 1
        db.session.commit()

        # Log Activity
        log_activity(
            user_id=current_user.id,
            file_id=file_record.id,
            action='DOWNLOAD',
            details=f"Downloaded '{file_record.original_name}' (shared by {share.sender.email})"
        )

    # Stream file to browser
    return send_file(
        io.BytesIO(decrypted_bytes),
        as_attachment=True,
        download_name=file_record.original_name,
        mimetype=file_record.mime_type or 'application/octet-stream'
    )


# -----------------------------------------------------------------------------
# Revoke & Delete Share API Route
# -----------------------------------------------------------------------------

@app.route('/api/share/<int:share_id>', methods=['DELETE', 'POST'])
@login_required
def api_revoke_or_delete_share(share_id: int):
    """
    Revoke access to a shared file or permanently delete it.
    Can only be performed by the sender of the share.
    Action:
    - 'revoke': marks share.is_active = False
    - 'delete': permanently deletes the share record; if no other shares reference the file, removes file from disk.
    """
    current_user = get_current_user()
    share = db.session.get(Share, share_id)

    if not share:
        return jsonify({'success': False, 'error': 'Share not found.'}), 404

    # Permission check: Only sender can revoke or delete
    if share.sender_id != current_user.id:
        return jsonify({'success': False, 'error': 'Only the owner/sender can revoke or delete this share.'}), 403

    action_type = request.args.get('action') or (request.get_json(silent=True) or {}).get('action') or 'revoke'
    file_record = share.file
    file_name = file_record.original_name if file_record else 'file'

    try:
        if action_type == 'revoke':
            share.is_active = False
            db.session.commit()
            log_activity(
                user_id=current_user.id,
                file_id=file_record.id if file_record else None,
                action='REVOKE',
                details=f"Revoked access to '{file_name}' for {share.receiver.email}"
            )
            return jsonify({'success': True, 'message': f"Access to '{file_name}' was successfully revoked."})

        elif action_type == 'delete':
            # Delete the share
            db.session.delete(share)
            db.session.commit()

            # Check if any other shares reference this file
            remaining_shares = Share.query.filter_by(file_id=file_record.id).count()
            if remaining_shares == 0:
                # Delete disk file
                delete_stored_file(file_record.stored_name, app.config['UPLOAD_FOLDER'])
                db.session.delete(file_record)
                db.session.commit()

            log_activity(
                user_id=current_user.id,
                file_id=None,
                action='DELETE',
                details=f"Deleted share for '{file_name}'"
            )
            return jsonify({'success': True, 'message': f"Share for '{file_name}' was deleted."})

        else:
            return jsonify({'success': False, 'error': f"Invalid action '{action_type}'. Use 'revoke' or 'delete'."}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"Operation failed: {str(e)}"}), 500


# -----------------------------------------------------------------------------
# Dashboard Summary & Activity Log Route
# -----------------------------------------------------------------------------

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    """
    Returns dashboard statistics:
    - total_sent: number of files shared by current user
    - total_received: number of files received by current user
    - active_shares: number of active shared files sent
    - total_storage: total bytes of uploaded files
    - recent_activity: last 10 activity logs for user actions or actions on their files
    """
    current_user = get_current_user()

    total_sent = Share.query.filter_by(sender_id=current_user.id).count()
    total_received = Share.query.filter_by(receiver_id=current_user.id).count()
    active_shares = Share.query.filter_by(sender_id=current_user.id, is_active=True).count()

    # Calculate total storage owned
    owned_files = File.query.filter_by(owner_id=current_user.id).all()
    total_storage = sum(f.file_size for f in owned_files)

    # Recent activities involving current user
    user_file_ids = [f.id for f in owned_files]
    recent_logs_query = ActivityLog.query.filter(
        (ActivityLog.user_id == current_user.id) | (ActivityLog.file_id.in_(user_file_ids))
    ).order_by(ActivityLog.timestamp.desc()).limit(10)

    recent_logs = recent_logs_query.all()

    return jsonify({
        'success': True,
        'stats': {
            'total_sent': total_sent,
            'total_received': total_received,
            'active_shares': active_shares,
            'total_storage_bytes': total_storage
        },
        'recent_activity': [log.to_dict() for log in recent_logs]
    })


# -----------------------------------------------------------------------------
# Error Handlers
# -----------------------------------------------------------------------------

@app.errorhandler(413)
def request_entity_too_large(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'File is too large. Maximum allowed size is 25MB.'}), 413
    return render_template('index.html', error='Uploaded file exceeded 25MB size limit.'), 413


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Requested resource not found.'}), 404
    return redirect(url_for('index'))


@app.errorhandler(500)
def internal_server_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'An internal server error occurred.'}), 500
    return redirect(url_for('index'))


# -----------------------------------------------------------------------------
# Main Application Entry Point
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    print(f"[*] Starting Secure Share application on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
