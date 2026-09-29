"""
Cryptographic Utilities Module for Secure Share
Implements Envelope Encryption using the Python `cryptography` library (Fernet / AES-128-CBC + HMAC-SHA256).

Envelope Encryption Explained for Project Viva:
1. Data Encryption Key (DEK): A unique, cryptographically strong random symmetric key is generated for every single file uploaded.
2. File Encryption: The plaintext file bytes are encrypted with the DEK using Fernet.
3. Key Encryption Key (KEK / Master Key): The DEK is encrypted using the master key kept securely in the environment (.env).
4. Storage: The encrypted file bytes are stored on disk with a random UUID name. The encrypted DEK is stored in the database.
   The original plaintext and the unencrypted DEK are never persisted on disk.
"""

import os
import uuid
from cryptography.fernet import Fernet
from config import Config


def get_master_fernet() -> Fernet:
    """
    Instantiate and return the master Fernet cipher using MASTER_ENCRYPTION_KEY from config.
    """
    key = Config.MASTER_ENCRYPTION_KEY
    if not key:
        raise ValueError("MASTER_ENCRYPTION_KEY is not configured in .env!")
    if isinstance(key, str):
        key = key.encode('utf-8')
    return Fernet(key)


def encrypt_dek(dek: bytes) -> str:
    """
    Encrypt a single-use Data Encryption Key (DEK) using the Master Key.
    Returns: URL-safe base64 string representation of the encrypted key.
    """
    master_cipher = get_master_fernet()
    encrypted_dek = master_cipher.encrypt(dek)
    return encrypted_dek.decode('utf-8')


def decrypt_dek(encrypted_dek_str: str) -> bytes:
    """
    Decrypt the master-encrypted DEK back into raw DEK bytes.
    """
    master_cipher = get_master_fernet()
    return master_cipher.decrypt(encrypted_dek_str.encode('utf-8'))


def allowed_file(filename: str) -> bool:
    """
    Verify whether the uploaded filename has an extension allowed in Config.ALLOWED_EXTENSIONS.
    Prevents execution of malicious scripts (.exe, .bat, .sh, .php, etc.)
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS


def encrypt_and_store_file(file_bytes: bytes, upload_folder: str) -> tuple[str, str, int]:
    """
    Encrypts raw file bytes with a newly generated DEK and writes the ciphertext to disk.
    
    Args:
        file_bytes: The raw plaintext bytes of the uploaded file.
        upload_folder: The directory where encrypted files should be saved.
        
    Returns:
        tuple (stored_name, encrypted_dek_str, file_size)
    """
    # 1. Generate a unique 32-byte single-use Data Encryption Key (DEK)
    dek = Fernet.generate_key()
    file_cipher = Fernet(dek)

    # 2. Encrypt the file data using Fernet (AES-128 in CBC mode + HMAC-SHA256)
    encrypted_data = file_cipher.encrypt(file_bytes)

    # 3. Generate a secure, unpredictable filename using UUIDv4
    stored_name = f"{uuid.uuid4().hex}.enc"
    file_path = os.path.join(upload_folder, stored_name)

    # 4. Write ciphertext to disk
    with open(file_path, 'wb') as f:
        f.write(encrypted_data)

    # 5. Encrypt the DEK using the master key (Envelope Encryption)
    encrypted_dek_str = encrypt_dek(dek)

    return stored_name, encrypted_dek_str, len(file_bytes)


def decrypt_stored_file(stored_name: str, encrypted_dek_str: str, upload_folder: str) -> bytes:
    """
    Reads the encrypted file from disk and decrypts it on-the-fly in memory.
    
    Args:
        stored_name: UUID filename of the encrypted file on disk.
        encrypted_dek_str: Master-encrypted DEK string from the database.
        upload_folder: Upload directory path.
        
    Returns:
        bytes: Decrypted original plaintext file bytes.
    """
    file_path = os.path.join(upload_folder, stored_name)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Encrypted file '{stored_name}' does not exist on server.")

    # 1. Decrypt the Data Encryption Key (DEK) with the master key
    dek = decrypt_dek(encrypted_dek_str)
    file_cipher = Fernet(dek)

    # 2. Read the ciphertext from disk
    with open(file_path, 'rb') as f:
        ciphertext = f.read()

    # 3. Decrypt ciphertext back to original bytes
    plaintext = file_cipher.decrypt(ciphertext)
    return plaintext


def delete_stored_file(stored_name: str, upload_folder: str) -> bool:
    """
    Safely delete the encrypted file from disk if it exists.
    """
    file_path = os.path.join(upload_folder, stored_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return True
        except OSError:
            return False
    return False
