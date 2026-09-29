"""
Packaging Script for Secure Share Project
Creates a clean, production-ready 'secure-share.zip' bundle containing all source files,
templates, static assets, configs, documentation, and tests.
"""

import os
import zipfile

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
ZIP_OUTPUT_NAME = "secure-share.zip"
ZIP_OUTPUT_PATH = os.path.join(PROJECT_ROOT, ZIP_OUTPUT_NAME)

# Files and directories to include
INCLUDE_ITEMS = [
    'app.py',
    'config.py',
    'models.py',
    'crypto_utils.py',
    'requirements.txt',
    '.env',
    '.env.example',
    '.gitignore',
    'schema_mysql.sql',
    'schema_postgresql.sql',
    'README.md',
    'test_app.py',
    'static',
    'templates',
    'uploads'
]

# Ensure uploads folder exists with a .gitkeep
uploads_dir = os.path.join(PROJECT_ROOT, 'uploads')
os.makedirs(uploads_dir, exist_ok=True)
gitkeep_path = os.path.join(uploads_dir, '.gitkeep')
if not os.path.exists(gitkeep_path):
    with open(gitkeep_path, 'w') as f:
        f.write('# Keep uploads directory in version control\n')

# Clean up any leftover test .enc files from uploads
for fname in os.listdir(uploads_dir):
    if fname.endswith('.enc'):
        try:
            os.remove(os.path.join(uploads_dir, fname))
        except OSError:
            pass


def create_zip():
    print(f"[*] Packaging Secure Share into '{ZIP_OUTPUT_NAME}'...")

    with zipfile.ZipFile(ZIP_OUTPUT_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for item in INCLUDE_ITEMS:
            item_path = os.path.join(PROJECT_ROOT, item)
            if not os.path.exists(item_path):
                print(f"[-] Warning: {item} not found, skipping.")
                continue

            if os.path.isfile(item_path):
                arcname = os.path.join('secure-share', item)
                zipf.write(item_path, arcname)
                print(f" [+] Added file: {arcname}")
            elif os.path.isdir(item_path):
                for root, dirs, files in os.walk(item_path):
                    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'venv', '.git')]
                    for file in files:
                        if file.endswith(('.pyc', '.pyo', '.db')) or (file.startswith('.') and file != '.gitkeep' and file != '.env'):
                            continue
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, PROJECT_ROOT)
                        arcname = os.path.join('secure-share', rel_path)
                        zipf.write(full_path, arcname)
                        print(f" [+] Added file: {arcname}")

    file_size_kb = os.path.getsize(ZIP_OUTPUT_PATH) / 1024
    print(f"\n[OK] Successfully generated '{ZIP_OUTPUT_NAME}' ({file_size_kb:.1f} KB)")
    print(f"     Location: {ZIP_OUTPUT_PATH}")


if __name__ == '__main__':
    create_zip()
