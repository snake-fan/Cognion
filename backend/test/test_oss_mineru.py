import argparse
import asyncio
import sys
from dataclasses import dataclass
import tyro
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import (
    ALIYUN_OSS_BUCKET,
    ALIYUN_OSS_ENABLED,
    ALIYUN_OSS_ENDPOINT,
    MINERU_API_URL,
    MINERU_ENABLED,
    call_mineru_api_with_pdf_url,
    upload_pdf_to_aliyun_oss,
)


@dataclass(frozen=True)
class Args:
    pdf_path: Path = Path("backend/storage/papers/ToM/074a0da890f344628bb5abe96267078b.pdf")


def _print_config_summary() -> None:
    print("[Config]")
    print(f"- MINERU_ENABLED: {MINERU_ENABLED}")
    print(f"- MINERU_API_URL set: {bool(MINERU_API_URL)}")
    print(f"- ALIYUN_OSS_ENABLED: {ALIYUN_OSS_ENABLED}")
    print(f"- ALIYUN_OSS_ENDPOINT set: {bool(ALIYUN_OSS_ENDPOINT)}")
    print(f"- ALIYUN_OSS_BUCKET set: {bool(ALIYUN_OSS_BUCKET)}")
    print()


async def run_test(pdf_path: Path) -> int:
    _print_config_summary()

    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"[Error] PDF file not found: {pdf_path}")
        return 2

    if pdf_path.suffix.lower() != ".pdf":
        print(f"[Warn] Target file is not .pdf suffix: {pdf_path.name}")

    pdf_bytes = pdf_path.read_bytes()
    print(f"[Step 1] Load file success: {pdf_path}")
    print(f"- file size: {len(pdf_bytes)} bytes")

    print("\n[Step 2] Upload to OSS...")
    oss_url = upload_pdf_to_aliyun_oss(pdf_bytes, pdf_path.name)
    if not oss_url:
        print("[Fail] OSS upload failed or URL generation failed.")
        print("- Check backend logs from services.py for exact reason.")
        return 3

    print("[OK] OSS upload succeeded.")
    print(f"- URL: {oss_url}")

    print("\n[Step 3] Call MinerU API...")
    mineru_text = await call_mineru_api_with_pdf_url(oss_url)
    if not mineru_text:
        print("[Fail] MinerU API call failed or returned empty text.")
        print("- Check backend logs from services.py for status/body details.")
        return 4

    print("[OK] MinerU API succeeded.")
    print(f"- text length: {len(mineru_text)}")
    preview = mineru_text[:500].replace("\n", " ")
    print(f"- preview: {preview}")

    print("\n[Done] OSS + MinerU chain is working.")
    return 0


def main() -> int:
    args = tyro.cli(Args)
    return asyncio.run(run_test(args.pdf_path))


if __name__ == "__main__":
    sys.exit(main())
