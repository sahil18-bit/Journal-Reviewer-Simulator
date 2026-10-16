"""The review pipeline: a chain of prompts, one prompt pattern per step."""

from __future__ import annotations

import json
import re
import time

from app.reviewer import prompts as P
from app.reviewer.llm import LLM, LLMError, parse_json
from app.reviewer.pdf_reader import Paper

RECOMMENDATIONS = ["Accept", "Minor Revision", "Major Revision", "Reject"]


# ---------------------------------------------------------------- fact check (step 3)
def _norm(text: str) -> str:
    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"(\w)- (\w)", r"\1\2", text)  # words broken across lines
    return re.sub(r"\s+", " ", text).strip(" .\"'")


def locate_quote(quote: str, paper: Paper) -> int | None:
    """Return the page where the quote appears, or None if it is not in the paper."""
    parts = [_norm(p) for p in re.split(r"\.\.\.|…", quote or "") if len(_norm(p)) >= 12]
    if not parts:
        return None
    for page_no, page in enumerate(paper.pages, 1):
        page_text = _norm(page)
        if all(part in page_text for part in parts):
            return page_no
    return None


def fact_check(findings: list[dict], paper: Paper) -> tuple[list[dict], list[dict]]:
    """Fact Check List pattern, enforced in code: keep only findings whose quote is real."""
    verified, rejected = [], []
    for f in findings:
        page = locate_quote(str(f.get("quote", "")), paper)
        if page is None:
            rejected.append({**f, "rejected_because": "quote not found in the paper"})
        else:
            verified.append({**f, "page": page})
    return verified, rejected


# ---------------------------------------------------------------- helpers
def _clean_finding(raw: dict, reviewer: str) -> dict | None:
    if not isinstance(raw, dict) or not raw.get("title"):
        return None
    severity = str(raw.get("severity", "minor")).lower()
    kind = str(raw.get("type", "missing")).lower()
    confidence = str(raw.get("confidence", "medium")).lower()
    return {
        "reviewer": reviewer,
        "title": str(raw["title"])[:200],
        "type": kind if kind in ("flaw", "missing") else "missing",
        "severity": severity if severity in ("major", "minor") else "minor",
        "quote": str(raw.get("quote", ""))[:600],
        "page": raw.get("page"),
        "why_it_matters": str(raw.get("why_it_matters", "")),
        "suggested_fix": str(raw.get("suggested_fix", "")),
        "confidence": confidence if confidence in ("high", "medium", "low") else "medium",
    }


def _integrity_note(summary: dict, paper: Paper) -> str:
    """Context Manager pattern result: report (never obey) instructions hidden in the paper."""
    quote = str(summary.get("instructions_to_reviewers_found", "")).strip()
    if not quote or quote.lower() in ("none", "no", "n/a") or locate_quote(quote, paper) is None:
        return ""
    return (
        "The manuscript contains text addressed to reviewers or AI systems, "
        f'which was ignored: "{quote}"'
    )


def _fallback_decision(findings: list[dict]) -> str:
    if any(f["severity"] == "major" for f in findings):
        return "Major Revision"
    return "Minor Revision" if findings else "Accept"


# ---------------------------------------------------------------- main chain
def run_review(paper: Paper, llm: LLM) -> dict:
    steps: list[dict] = []
    paper_text = paper.as_prompt_text()

    def record(name: str, patterns: str, started: float, note: str = "") -> None:
        steps.append(
            {
                "step": name,
                "patterns": patterns,
                "seconds": round(time.time() - started, 1),
                "note": note,
            }
        )

    # Step 1: Paper Analyst (Persona + Template + Context Manager)
    t = time.time()
    summary = parse_json(
        llm.ask(
            P.ANALYST_SYSTEM,
            P.ANALYST_PROMPT.format(
                rules=P.PAPER_RULES, template=P.ANALYST_TEMPLATE, paper=paper_text
            ),
        )
    )
    record("1. Paper analyst", "Persona, Template, Context Manager", t)

    # Step 2: three specialist reviewers (Cognitive Verifier + Persona + Few-shot + CoT + Template)
    candidates: list[dict] = []
    for name, spec in P.REVIEWERS.items():
        t = time.time()
        prompt = P.REVIEWER_PROMPT.format(
            rules=P.PAPER_RULES,
            question=spec["question"],
            checklist="\n".join(f"- {item}" for item in spec["checklist"]),
            examples=spec["examples"],
            summary=json.dumps(summary, indent=1)[:4000],
            template=P.FINDING_TEMPLATE,
            paper=paper_text,
        )
        try:
            raw = parse_json(llm.ask(spec["persona"], prompt)).get("findings", [])
        except LLMError:
            raw = []
            record(
                f"2. {name.title()} reviewer",
                "Cognitive Verifier, Persona, Few-shot, Chain of Thought, Template",
                t,
                "reply could not be parsed",
            )
            continue
        found = [
            c
            for c in (_clean_finding(r, name) for r in (raw if isinstance(raw, list) else []))
            if c
        ]
        candidates += found
        record(
            f"2. {name.title()} reviewer",
            "Cognitive Verifier, Persona, Few-shot, Chain of Thought, Template",
            t,
            f"{len(found)} finding(s)",
        )

    # Step 3: Fact Check List - every quote must exist in the PDF text
    t = time.time()
    verified, rejected = fact_check(candidates, paper)
    for i, f in enumerate(verified, 1):
        f["id"] = f"F{i}"
    record(
        "3. Fact check", "Fact Check List", t, f"{len(verified)} verified, {len(rejected)} rejected"
    )

    # Step 4: Handling editor (Persona + Recipe + Reflection + Template + Tail Generation)
    t = time.time()
    compact = [
        {
            k: f[k]
            for k in (
                "id",
                "reviewer",
                "title",
                "type",
                "severity",
                "quote",
                "page",
                "why_it_matters",
                "confidence",
            )
        }
        for f in verified
    ]
    try:
        editor = parse_json(
            llm.ask(
                P.EDITOR_SYSTEM,
                P.EDITOR_PROMPT.format(
                    summary=json.dumps(summary, indent=1)[:4000],
                    findings=json.dumps(compact, indent=1),
                ),
            )
        )
        note = ""
    except LLMError:
        editor, note = {}, "editor reply could not be parsed; rule-based fallback used"
    record("4. Handling editor", "Persona, Recipe, Reflection, Template, Tail Generation", t, note)

    by_id = {f["id"]: f for f in verified}
    major_ids = [i for i in editor.get("major_concern_ids", []) if i in by_id]
    minor_ids = [
        i for i in editor.get("minor_concern_ids", []) if i in by_id and i not in major_ids
    ]
    if not major_ids and not minor_ids:  # editor gave nothing usable -> use reviewer severities
        major_ids = [f["id"] for f in verified if f["severity"] == "major"]
        minor_ids = [f["id"] for f in verified if f["severity"] == "minor"]
    merged = [f["id"] for f in verified if f["id"] not in major_ids + minor_ids]
    for i in major_ids:
        by_id[i]["severity"] = "major"
    for i in minor_ids:
        by_id[i]["severity"] = "minor"

    recommendation = editor.get("recommendation")
    if recommendation not in RECOMMENDATIONS:
        recommendation = _fallback_decision([by_id[i] for i in major_ids + minor_ids])

    return {
        "paper": {
            "filename": paper.filename,
            "pages": len(paper.pages),
            "title": summary.get("title") or paper.filename,
        },
        "paper_summary": summary,
        "recommendation": recommendation,
        "decision_reasoning": str(
            editor.get(
                "decision_reasoning", "Decided from reviewer severities (editor step unavailable)."
            )
        ),
        "overall_summary": str(editor.get("overall_summary", "")),
        "strengths": [str(s) for s in editor.get("strengths", [])][:8],
        "major_concerns": [by_id[i] for i in major_ids],
        "minor_concerns": [by_id[i] for i in minor_ids],
        "merged_duplicates": merged,
        "questions_to_authors": [str(q) for q in editor.get("questions_to_authors", [])][:5],
        "unverified_findings": rejected,
        "integrity_note": _integrity_note(summary, paper),
        "steps": steps,
        "disclaimer": (
            "Simulated review generated by an AI pipeline. "
            "It supports, but does not replace, expert peer review."
        ),
    }


# ------------------------------------------------- Deep Technical Critique (Template)
def to_markdown(report: dict) -> str:
    def block(f: dict) -> str:
        evidence = f'- Evidence (page {f["page"]}): "{f["quote"]}"\n' if f["quote"] else ""
        return (
            f"**{f['id']}. {f['title']}** "
            f"({f['reviewer']}, {f['type']}, confidence: {f['confidence']})\n\n"
            f"{evidence}"
            f"- Why it matters: {f['why_it_matters']}\n"
            f"- Required action: {f['suggested_fix']}\n"
        )

    lines = [
        "# Deep Technical Critique",
        f"**Paper:** {report['paper']['title']}  ",
        f"**File:** {report['paper']['filename']} ({report['paper']['pages']} pages)",
        "",
        "## 1. Summary of the submission",
        report["overall_summary"] or report["paper_summary"].get("research_question", ""),
        "",
        f"## 2. Recommendation: {report['recommendation']}",
        report["decision_reasoning"],
        "",
        *(
            [f"**Note to editor:** {report['integrity_note']}", ""]
            if report.get("integrity_note")
            else []
        ),
        "## 3. Strengths",
        *(f"- {s}" for s in report["strengths"] or ["None listed."]),
        "",
        "## 4. Major concerns",
        *(block(f) for f in report["major_concerns"]),
        *([] if report["major_concerns"] else ["None."]),
        "",
        "## 5. Minor concerns",
        *(block(f) for f in report["minor_concerns"]),
        *([] if report["minor_concerns"] else ["None."]),
        "",
        "## 6. Questions to the authors",
        *(f"{i}. {q}" for i, q in enumerate(report["questions_to_authors"], 1)),
        "",
        "## 7. Fact check",
        f"{len(report['major_concerns']) + len(report['minor_concerns'])} finding(s) "
        "verified against the PDF text; "
        f"{len(report['unverified_findings'])} rejected because their quotes were not found.",
        "",
        f"*{report['disclaimer']}*",
    ]
    return "\n".join(lines)
