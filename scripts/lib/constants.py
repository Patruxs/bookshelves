from __future__ import annotations

import re

BOOKS_DIR = "Books"
INBOX_DIR = "Inbox"
BACKUP_DIR = ".backups"
DATA_JSON = "data/data.json"
COVER_DIR = "assets/covers"
COVER_EXTENSION = ".webp"
BOOK_EXTENSIONS = {".pdf", ".epub", ".docx"}
EXTENSION_PRIORITY = {".pdf": 0, ".epub": 1, ".docx": 2}
DEFAULT_RELEASE_TAG = "storage-v1"
COVER_WIDTH = 600
COVER_QUALITY = 85
COVER_FORMAT = "webp"
COVER_SIZE_WARNING_BYTES = 80 * 1024
MAX_DATA_BACKUPS = 20
CATEGORY_PATTERN = re.compile(r"^(\d+)_(.+)$")
SAFE_ASSET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
