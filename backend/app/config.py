import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / 'storage'
UPLOADS_DIR = STORAGE_DIR / 'uploads'
PREVIEWS_DIR = STORAGE_DIR / 'previews'
DATABASE_PATH = BASE_DIR / 'data' / 'app.db'

for directory in (STORAGE_DIR, UPLOADS_DIR, PREVIEWS_DIR, DATABASE_PATH.parent):
    directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings():
    return {
        'app_name': os.getenv('APP_NAME', 'Wiring Extraction Platform'),
        'api_version': os.getenv('API_VERSION', 'v1'),
        'database_url': os.getenv('DATABASE_URL', f'sqlite:///{DATABASE_PATH}'),
        'max_upload_size_mb': int(os.getenv('MAX_UPLOAD_SIZE_MB', '25')),
        'cors_origins': os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(','),
        'llm_api_key': os.getenv('LLM_API_KEY', ''),
        'llm_provider': os.getenv('LLM_PROVIDER', 'openai'),
    }
