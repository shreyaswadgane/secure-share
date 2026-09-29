-- =====================================================================
-- Secure Share - PostgreSQL Database Schema
-- Compatible with PostgreSQL 12, 13, 14, 15, 16+
-- =====================================================================

-- 1. Create Database (Run separately if needed in psql)
-- CREATE DATABASE secureshare WITH ENCODING 'UTF8';
-- \c secureshare;

-- ---------------------------------------------------------------------
-- Table 1: users
-- Stores registered users and hashed authentication credentials
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- ---------------------------------------------------------------------
-- Table 2: files
-- Stores uploaded file metadata and encrypted Data Encryption Keys (DEKs).
-- The actual ciphertext blob resides encrypted on disk under stored_name.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS files (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(64) NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100) DEFAULT 'application/octet-stream',
    encryption_key_ref TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_files_owner_id ON files (owner_id);
CREATE INDEX IF NOT EXISTS idx_files_stored_name ON files (stored_name);

-- ---------------------------------------------------------------------
-- Table 3: shares
-- Represents access permissions between sender and recipient.
-- Enforces expiration dates, download quotas, and optional passphrases.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS shares (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id INT NOT NULL REFERENCES files(id) ON DELETE CASCADE ON UPDATE CASCADE,
    sender_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    receiver_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    share_password_hash VARCHAR(256) DEFAULT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
    max_downloads INT DEFAULT NULL,
    download_count INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_shares_file_id ON shares (file_id);
CREATE INDEX IF NOT EXISTS idx_shares_sender_id ON shares (sender_id);
CREATE INDEX IF NOT EXISTS idx_shares_receiver_id ON shares (receiver_id);
CREATE INDEX IF NOT EXISTS idx_shares_is_active ON shares (is_active);

-- ---------------------------------------------------------------------
-- Table 4: activity_logs
-- Immutable audit trail recording sensitive security events.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_logs (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    file_id INT DEFAULT NULL REFERENCES files(id) ON DELETE SET NULL ON UPDATE CASCADE,
    action VARCHAR(50) NOT NULL,
    details VARCHAR(255) DEFAULT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE INDEX IF NOT EXISTS idx_logs_user_id ON activity_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_logs_file_id ON activity_logs (file_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON activity_logs (timestamp);
