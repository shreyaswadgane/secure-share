-- =====================================================================
-- Secure Share - MySQL Database Schema
-- Compatible with MySQL 5.7+ / 8.0+ and MariaDB 10.3+
-- Engine: InnoDB (supports ACID transactions and Foreign Keys)
-- Character Set: utf8mb4 (supports full Unicode & emojis)
-- =====================================================================

-- 1. Create Database
CREATE DATABASE IF NOT EXISTS `secureshare`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `secureshare`;

-- ---------------------------------------------------------------------
-- Table 1: users
-- Stores registered users and hashed authentication credentials
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `password_hash` VARCHAR(256) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_users_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 2: files
-- Stores uploaded file metadata and encrypted Data Encryption Keys (DEKs).
-- The actual ciphertext blob resides encrypted on disk under stored_name.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `files` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `owner_id` INT NOT NULL,
    `original_name` VARCHAR(255) NOT NULL,
    `stored_name` VARCHAR(64) NOT NULL UNIQUE,
    `file_size` BIGINT NOT NULL,
    `mime_type` VARCHAR(100) DEFAULT 'application/octet-stream',
    `encryption_key_ref` TEXT NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_files_owner`
        FOREIGN KEY (`owner_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX `idx_files_owner_id` (`owner_id`),
    INDEX `idx_files_stored_name` (`stored_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 3: shares
-- Represents access permissions between sender and recipient.
-- Enforces expiration dates, download quotas, and optional passphrases.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `shares` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `file_id` INT NOT NULL,
    `sender_id` INT NOT NULL,
    `receiver_id` INT NOT NULL,
    `share_password_hash` VARCHAR(256) DEFAULT NULL,
    `expires_at` DATETIME DEFAULT NULL,
    `max_downloads` INT DEFAULT NULL,
    `download_count` INT NOT NULL DEFAULT 0,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_shares_file`
        FOREIGN KEY (`file_id`) REFERENCES `files` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `fk_shares_sender`
        FOREIGN KEY (`sender_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `fk_shares_receiver`
        FOREIGN KEY (`receiver_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    INDEX `idx_shares_file_id` (`file_id`),
    INDEX `idx_shares_sender_id` (`sender_id`),
    INDEX `idx_shares_receiver_id` (`receiver_id`),
    INDEX `idx_shares_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- Table 4: activity_logs
-- Immutable audit trail recording sensitive security events.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `activity_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `file_id` INT DEFAULT NULL,
    `action` VARCHAR(50) NOT NULL,
    `details` VARCHAR(255) DEFAULT NULL,
    `timestamp` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_logs_user`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `fk_logs_file`
        FOREIGN KEY (`file_id`) REFERENCES `files` (`id`)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    INDEX `idx_logs_user_id` (`user_id`),
    INDEX `idx_logs_file_id` (`file_id`),
    INDEX `idx_logs_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
