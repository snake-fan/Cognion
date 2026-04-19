import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_SIMILARITY_MODEL = os.getenv("OPENAI_SIMILARITY_MODEL", "gpt-4.1-mini")
OPENAI_MERGE_MODEL = os.getenv("OPENAI_MERGE_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1")

PDF_STORAGE_DIR = os.getenv("PDF_STORAGE_DIR", str(Path(__file__).resolve().parents[2] / "storage" / "papers"))
NOTE_STORAGE_DIR = os.getenv("NOTE_STORAGE_DIR", str(Path(__file__).resolve().parents[2] / "storage" / "notes"))

MINERU_ENABLED = os.getenv("MINERU_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
MINERU_API_URL = os.getenv("MINERU_API_URL", "")
MINERU_API_KEY = os.getenv("MINERU_API_KEY", "")
MINERU_MODEL = os.getenv("MINERU_MODEL", "pdf_url")
MINERU_TIMEOUT_SECONDS = int(os.getenv("MINERU_TIMEOUT_SECONDS", "180"))
MINERU_POLL_INTERVAL_SECONDS = float(os.getenv("MINERU_POLL_INTERVAL_SECONDS", "3"))
MINERU_MAX_CHARS = int(os.getenv("MINERU_MAX_CHARS", "100000"))

ALIYUN_OSS_ENABLED = os.getenv("ALIYUN_OSS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
ALIYUN_OSS_ENDPOINT = os.getenv("ALIYUN_OSS_ENDPOINT", "")
ALIYUN_OSS_BUCKET = os.getenv("ALIYUN_OSS_BUCKET", "")
ALIYUN_OSS_ACCESS_KEY_ID = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "")
ALIYUN_OSS_ACCESS_KEY_SECRET = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "")
ALIYUN_OSS_KEY_PREFIX = os.getenv("ALIYUN_OSS_KEY_PREFIX", "cognion/mineru")
ALIYUN_OSS_PUBLIC_BASE_URL = os.getenv("ALIYUN_OSS_PUBLIC_BASE_URL", "")
ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS = int(os.getenv("ALIYUN_OSS_SIGNED_URL_EXPIRES_SECONDS", "900"))
