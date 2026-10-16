"""Review endpoint: drop a paper, get a review."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.reviewer.checklist import review_with_checklist
from app.reviewer.llm import DEFAULT_MODELS, LLM, HttpLLM, LLMError, guess_provider
from app.reviewer.pdf_reader import PaperError, read_pdf
from app.reviewer.pipeline import run_review, to_markdown

router = APIRouter(prefix="/reviews", tags=["reviews"])


def get_llm(settings: Settings = Depends(get_settings)) -> Optional[LLM]:
    """AI client from the saved settings (.env). None means no key is set."""
    if settings.llm_provider == "none" or not settings.llm_api_key:
        return None
    return HttpLLM(settings.llm_provider, settings.llm_api_key, settings.llm_model)


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"code": f"http_{status}", "message": message}}
    )


@router.get("/config")
def review_config(llm: Optional[LLM] = Depends(get_llm)) -> dict:
    return {"ai_enabled": llm is not None}


@router.post("")
def create_review(
    file: UploadFile = File(...),
    provider: str = Form(""),
    api_key: str = Form(""),
    llm: Optional[LLM] = Depends(get_llm),
    settings: Settings = Depends(get_settings),
):
    """Review a PDF with the AI reviewers; without a working AI, use the built-in checklist."""
    if api_key.strip():  # key typed on the page: used for this request only, never stored
        chosen = provider if provider in DEFAULT_MODELS else guess_provider(api_key)
        llm = HttpLLM(chosen, api_key.strip())
    try:
        data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        paper = read_pdf(
            data, file.filename or "paper.pdf", settings.max_upload_mb, settings.max_pages
        )
    except PaperError as exc:
        return _error(exc.status_code, exc.message)

    if llm is not None:
        try:
            report = run_review(paper, llm)
            report["mode"] = "ai"
        except LLMError:
            report = review_with_checklist(paper)
            report["decision_reasoning"] += (
                " (The AI service could not be reached, so the built-in checklist was used."
                " Check the API key and the internet connection.)"
            )
    else:
        report = review_with_checklist(paper)
        report["decision_reasoning"] += (
            " (Reviewed with the built-in checklist; add an AI key for the full AI review.)"
        )
    report["markdown"] = to_markdown(report)
    return report
