from fastapi import APIRouter, File, Form, UploadFile

from .services import answer_with_context

router = APIRouter()


@router.post("/ask")
async def ask_about_quote(
    question: str = Form(...),
    quote: str = Form(default=""),
    pdf_file: UploadFile | None = File(default=None),
) -> dict[str, str]:
    pdf_bytes = await pdf_file.read() if pdf_file else None
    response_text = await answer_with_context(
        question=question,
        quote=quote,
        pdf_bytes=pdf_bytes,
        pdf_filename=pdf_file.filename if pdf_file else None,
    )

    return {"answer": response_text}
