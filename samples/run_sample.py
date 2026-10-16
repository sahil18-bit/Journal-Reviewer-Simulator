"""Replays the saved model replies in sample_run/ through the real pipeline and
writes the prompts that were sent, the JSON result and the Markdown report.

    python3 samples/run_sample.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.reviewer import prompts as P  # noqa: E402
from app.reviewer.pdf_reader import read_pdf  # noqa: E402
from app.reviewer.pipeline import run_review, to_markdown  # noqa: E402

SAMPLE_PAPER = HERE / "sample_paper.pdf"
RUN = HERE / "sample_run"


class ReplayLLM:
    """Returns the saved AI reply for each step and remembers the prompt it was given."""

    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    def ask(self, system: str, prompt: str) -> str:
        if system == P.ANALYST_SYSTEM:
            name = "1_analyst"
        elif system == P.EDITOR_SYSTEM:
            name = "4_editor"
        else:
            name = "2_" + next(k for k, v in P.REVIEWERS.items() if v["persona"] == system)
        self.prompts.append((name, f"SYSTEM:\n{system}\n\nUSER:\n{prompt}"))
        return (RUN / f"{name}.json").read_text(encoding="utf-8")


def main() -> None:
    paper = read_pdf(SAMPLE_PAPER.read_bytes(), "sample_paper.pdf")
    llm = ReplayLLM()
    report = run_review(paper, llm)
    (RUN / "prompts").mkdir(exist_ok=True)
    for name, text in llm.prompts:
        (RUN / "prompts" / f"{name}.txt").write_text(text, encoding="utf-8")
    (HERE / "sample_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (HERE / "sample_report.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))


if __name__ == "__main__":
    main()
