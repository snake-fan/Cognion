import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5555").rstrip("/")
JWT_SECRET = os.getenv("JWT_SECRET", "development-only-change-me")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))
ONE_TIME_TOKEN_MINUTES = int(os.getenv("ONE_TIME_TOKEN_MINUTES", "30"))
UNVERIFIED_USER_RETENTION_DAYS = int(os.getenv("UNVERIFIED_USER_RETENTION_DAYS", "7"))
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5555").split(",") if origin.strip()
]

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "no-reply@cognion.local")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() in {"1", "true", "yes", "on"}
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}

LLM_INVOCATION_LOG_MODE = os.getenv(
    "LLM_INVOCATION_LOG_MODE", "off" if IS_PRODUCTION else "full"
).strip().lower()
if LLM_INVOCATION_LOG_MODE not in {"off", "metadata", "full"}:
    LLM_INVOCATION_LOG_MODE = "off" if IS_PRODUCTION else "full"
LLM_INVOCATION_LOG_RETENTION_DAYS = int(os.getenv("LLM_INVOCATION_LOG_RETENTION_DAYS", "7"))

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
