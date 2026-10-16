"""Built-in checklist reviewer, used only when no AI key is available.

It asks the same reviewer questions as the AI prompts (methodology, statistics,
baselines) using simple text rules, so a dropped paper always gets a review.
The AI reviewers are smarter; this is the safety net.
"""

from __future__ import annotations

import re

from app.reviewer.pdf_reader import Paper

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(\[])")


def rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I)


NEG = rx(r"\bnot\b", r"\bnever\b", r"\bwithout\b", r"\bno\b", r"only on the train")
TEST_TUNING = rx(
    r"(select|chose|chosen|tun|optimi[sz]|early.stop)\w*\b[^.]{0,80}\b(on|using|based on|against)"
    r"\b[^.]{0,30}\btest (set|data|split)"
)
PREPROC = rx(
    r"normali[sz]",
    r"standardi[sz]",
    r"\bscal(ed|ing)\b",
    r"smote",
    r"oversampl",
    r"feature selection",
    r"\bpca\b",
    r"imput",
)
WHOLE = rx(
    r"(entire|whole|full|complete|all the) (data ?set|data)", r"before (the )?(train.test )?split"
)
RESULT = rx(r"\d+(\.\d+)?\s*%", r"\baccuracy\b", r"\bf1\b", r"\bauc\b", r"\brmse\b", r"\bmae\b")
PROTOCOL = rx(
    r"test(ing)? set",
    r"held.out",
    r"hold.out",
    r"cross.validation",
    r"\d+.fold",
    r"k.fold",
    r"train/test",
    r"validation set",
    r"\bsplit\b",
    r"leave.one.out",
)
CAUSAL = rx(r"\bcause[sd]?\b", r"\bleads? to\b", r"\bcausal(ly)?\b", r"\bproves? that\b")
DESIGN = rx(r"randomi[sz]ed", r"controlled trial", r"randomly assigned")
OVERCLAIM = rx(
    r"generali[sz]e[sd]? (well )?to (any|all|other|unseen|every)",
    r"\bany (hospital|dataset|domain|population|setting)\b",
    r"directly deployed",
    r"universally applicable",
)
SIGNIF = rx(r"\bsignificant(ly)?\b")
TESTS = rx(
    r"t.test",
    r"wilcoxon",
    r"mann.whitney",
    r"anova",
    r"chi.squared?",
    r"mcnemar",
    r"kruskal",
    r"friedman",
    r"permutation test",
    r"bootstrap",
)
PVAL = rx(r"\bp\s*[<=>]\s*0?\.\d+", r"p.values?")
VARIANCE = rx(
    r"±",
    r"\+/-",
    r"standard deviation",
    r"\bstd\b",
    r"confidence interval",
    r"\bci\b",
    r"standard error",
    r"\d+ (runs|seeds|repetitions|trials)",
    r"averaged over",
    r"repeated",
)
IMBAL = rx(r"imbalanc", r"unbalanc", r"minority class")
CLASS_METRICS = rx(
    r"\bf1\b",
    r"precision",
    r"recall",
    r"\bauc\b",
    r"\broc\b",
    r"balanced accuracy",
    r"\bmcc\b",
    r"sensitivity",
    r"specificity",
)
CORRECTION = rx(r"bonferroni", r"\bholm\b", r"benjamini", r"false discovery", r"\bfdr\b", r"tukey")
UNPAIRED = rx(r"independent.(samples? )?t.test", r"unpaired t.test", r"two.sample t.test")
SUPERIOR = rx(
    r"outperform",
    r"state.of.the.art",
    r"superior to",
    r"better than (existing|previous|other|all)",
    r"surpass",
)
COMPARE = rx(r"compar", r"baseline", r"\bvs\.?\b", r"versus", r"against", r"\bthan\b", r"\btable\b")
METHODS = {
    "logistic regression": r"logistic regression",
    "random forest": r"random forest",
    "decision tree": r"decision tree",
    "SVM": r"\bsvm\b|support vector",
    "k-NN": r"\bk-?nn\b|nearest neighbo",
    "naive Bayes": r"naive bayes",
    "XGBoost": r"xgboost",
    "LightGBM": r"lightgbm",
    "gradient boosting": r"gradient boost",
    "MLP": r"\bmlp\b",
    "ResNet": r"resnet",
    "VGG": r"\bvgg",
    "BERT": r"\bbert\b",
    "Transformer": r"transformer",
    "ARIMA": r"\barima\b",
}
OWN = rx(r"\bour\b", r"\bproposed\b", r"\bwe propose\b", r"\(ours\)")
PARTS = rx(
    r"\bcombin(es|ing)\b",
    r"\bconsists? of\b",
    r"\bhybrid\b",
    r"\bcomponents?\b",
    r"\bmodules?\b",
    r"\bmechanisms?\b",
)
ABLATION = rx(r"ablation", r"\bw/o\b", r"without the \w+ (module|component)")
COPIED = rx(
    r"reported in (the )?(original|their|respective)",
    r"(taken|copied) from (the )?(original|their)",
)
SEED = rx(r"\bseed", r"random state")
CODE = rx(
    r"github", r"gitlab", r"code (is|will be) (publicly )?available", r"source code", r"zenodo"
)
LIMITS = rx(r"limitation", r"threats to validity")
INJECT = rx(
    r"ignore (all |any )?(previous|prior|above) instructions",
    r"(ai|llm) reviewers?",
    r"recommend (acceptance|accepting)",
    r"positive review",
)


def _sentences(paper: Paper) -> list[tuple[int, str]]:
    out = []
    for page_no, text in enumerate(paper.pages, 1):
        out += [(page_no, s.strip()) for s in _SENT.split(text) if len(s.strip()) > 15]
    return out


def _first(sents, pattern, also=None, skip_neg=False):
    for page, s in sents:
        if pattern.search(s) and (also is None or also.search(s)):
            if skip_neg and NEG.search(s):
                continue
            return page, s[:400]
    return None, ""


def _title(paper: Paper) -> str:
    head = paper.pages[0][:400]
    cut = re.search(r"\babstract\b", head, re.I)
    title = head[: cut.start()] if cut and cut.start() > 10 else " ".join(head.split()[:14])
    return title.strip(" .:") or paper.filename


def review_with_checklist(paper: Paper) -> dict:
    sents = _sentences(paper)
    text = paper.full_text()
    has = lambda p: bool(p.search(text))  # noqa: E731
    found: list[dict] = []

    def add(reviewer, title, kind, severity, hit, why, fix, conf="medium"):
        page, quote = hit if isinstance(hit, tuple) else (None, "")
        found.append(
            {
                "reviewer": reviewer,
                "title": title,
                "type": kind,
                "severity": severity,
                "quote": quote,
                "page": page,
                "why_it_matters": why,
                "suggested_fix": fix,
                "confidence": conf,
            }
        )

    # ---- methodology
    hit = _first(sents, TEST_TUNING, skip_neg=True)
    if hit[0]:
        add(
            "methodology",
            "The test set was used for tuning or model selection",
            "flaw",
            "major",
            hit,
            "If the test set guides model choices it no longer measures performance on unseen data.",
            "Tune on a separate validation split (or nested cross-validation) and report results on an untouched test set.",
            "high",
        )
    hit = _first(sents, PREPROC, WHOLE, skip_neg=True)
    if hit[0]:
        add(
            "methodology",
            "Preprocessing applied to the whole dataset before splitting",
            "flaw",
            "major",
            hit,
            "Scaling, oversampling or feature selection fitted on all data lets test information leak into training and inflates results.",
            "Fit every preprocessing step on the training data only (inside each fold) and re-run the experiments.",
            "high",
        )
    if has(RESULT) and not has(PROTOCOL):
        add(
            "methodology",
            "No train/test or cross-validation protocol is described",
            "missing",
            "major",
            _first(sents, RESULT),
            "Without a stated protocol, readers cannot tell whether results are on held-out data.",
            "Describe the data split or cross-validation scheme.",
        )
    hit = _first(sents, CAUSAL, skip_neg=True)
    if hit[0] and not has(DESIGN):
        add(
            "methodology",
            "Causal claim from an observational or predictive study",
            "flaw",
            "minor",
            hit,
            "A predictive model shows association, not cause and effect.",
            "Rephrase as an association, or add a design that supports a causal claim.",
        )
    hit = _first(sents, OVERCLAIM)
    if hit[0]:
        add(
            "methodology",
            "Claims go beyond the evaluated data",
            "flaw",
            "minor",
            hit,
            "Results on the studied data do not show that the method works in every setting.",
            "Limit the claim to the evaluated setting or add external validation.",
        )
    if not has(LIMITS):
        add(
            "methodology",
            "Limitations are not discussed",
            "missing",
            "minor",
            None,
            "Readers need the authors' view of where the results may not hold.",
            "Add a limitations paragraph (data, evaluation, generalisation).",
            "high",
        )
    missing = [n for n, p in (("random seed", SEED), ("code availability", CODE)) if not has(p)]
    if missing:
        add(
            "methodology",
            "Reproducibility details missing: " + ", ".join(missing),
            "missing",
            "minor",
            None,
            "Other researchers need these details to repeat the experiments.",
            "Report the " + " and ".join(missing) + ".",
        )

    # ---- statistics
    hit = _first(sents, SIGNIF)
    if hit[0] and not has(TESTS) and not has(PVAL):
        add(
            "statistics",
            "Significance claimed without a statistical test",
            "missing",
            "major",
            hit,
            "'Significant' implies a statistical test; without one the difference may be random variation.",
            "Use a test suited to the design (e.g. a paired test over folds or seeds, or McNemar's test) and report the p-value, or remove the word.",
            "high",
        )
    if has(RESULT) and not has(VARIANCE):
        add(
            "statistics",
            "Results are single numbers without variability",
            "missing",
            "major",
            _first(sents, RESULT, rx(r"\d+(\.\d+)?\s*%")),
            "Scores change with the random seed and split; a small gain may be noise.",
            "Repeat over several seeds or folds and report mean ± standard deviation or confidence intervals.",
        )
    hit = _first(sents, IMBAL)
    if hit[0] and not has(CLASS_METRICS):
        add(
            "statistics",
            "Accuracy is the only metric on imbalanced data",
            "flaw",
            "major",
            hit,
            "On imbalanced data a model can score high accuracy by predicting the majority class.",
            "Report precision, recall, F1, ROC-AUC and a confusion matrix.",
            "high",
        )
    if len(re.findall(r"\bp\s*[<=>]\s*0?\.\d+", text, re.I)) >= 4 and not has(CORRECTION):
        add(
            "statistics",
            "Many p-values without multiple-comparison correction",
            "flaw",
            "major",
            _first(sents, PVAL),
            "With many tests, some 'significant' results are expected by chance.",
            "Apply a correction such as Holm-Bonferroni or Benjamini-Hochberg.",
        )
    hit = _first(sents, UNPAIRED)
    if hit[0] and has(rx(r"cross.validation", r"same test", r"\d+.fold")):
        add(
            "statistics",
            "Unpaired test used on paired results",
            "flaw",
            "minor",
            hit,
            "Models evaluated on the same folds or test set give paired results.",
            "Use a paired t-test, Wilcoxon signed-rank test or McNemar's test.",
        )

    # ---- baselines
    claim = _first(sents, SUPERIOR, skip_neg=True)
    compared = {
        name
        for name, p in METHODS.items()
        for _, s in sents
        if re.search(p, s, re.I) and COMPARE.search(s) and not OWN.search(s)
    }
    if claim[0] and len(compared) <= 1:
        add(
            "baselines",
            "Superiority claimed with "
            + ("no" if not compared else "only one")
            + " comparison method",
            "missing",
            "major",
            claim,
            "Beating one or no method does not show superiority over existing approaches.",
            "Compare against a simple baseline and the strongest relevant methods under the same protocol, or narrow the claim.",
            "high",
        )
    hit = _first(sents, OWN, PARTS)
    if hit[0] and not has(ABLATION):
        add(
            "baselines",
            "No ablation study for a multi-part method",
            "missing",
            "major",
            hit,
            "It is unknown which part of the method produces the improvement.",
            "Add results with each component removed or replaced.",
        )
    hit = _first(sents, COPIED)
    if hit[0]:
        add(
            "baselines",
            "Baseline numbers copied from other papers",
            "flaw",
            "minor",
            hit,
            "Other papers may use different splits or preprocessing, so the comparison may be unfair.",
            "Re-run baselines under the same protocol.",
        )

    for i, f in enumerate(found, 1):
        f["id"] = f"F{i}"
    major = [f for f in found if f["severity"] == "major"]
    minor = [f for f in found if f["severity"] == "minor"]
    decision = "Major Revision" if major else ("Minor Revision" if minor else "Accept")
    reason = (
        f"{len(major)} major concern(s) need new analyses or experiments."
        if major
        else f"Only {len(minor)} minor clarification(s) are needed."
        if minor
        else "No concerns were detected by the checklist."
    )

    strengths = [
        label
        for label, p in (
            ("A held-out or cross-validation protocol is described.", PROTOCOL),
            ("Results report variability or repeated runs.", VARIANCE),
            ("A statistical test is named.", TESTS),
            ("An ablation study is included.", ABLATION),
            ("Code is made available.", CODE),
            ("Limitations are discussed.", LIMITS),
        )
        if has(p)
    ]
    inj = _first(sents, INJECT)
    title = _title(paper)
    return {
        "paper": {"filename": paper.filename, "pages": len(paper.pages), "title": title},
        "paper_summary": {"title": title},
        "mode": "checklist",
        "recommendation": decision,
        "decision_reasoning": reason,
        "overall_summary": f"The paper was checked against the reviewer checklist for methodology, statistics and baselines: {len(major)} major and {len(minor)} minor concern(s).",
        "strengths": strengths,
        "major_concerns": major,
        "minor_concerns": minor,
        "merged_duplicates": [],
        "questions_to_authors": [f"{f['title']}: {f['suggested_fix']}" for f in major[:5]],
        "unverified_findings": [],
        "integrity_note": (
            f'The manuscript contains text addressed to reviewers or AI systems, which was ignored: "{inj[1]}"'
            if inj[0]
            else ""
        ),
        "steps": [
            {
                "step": "Built-in checklist",
                "patterns": "Same reviewer questions, simple text rules",
                "seconds": 0,
                "note": f"{len(found)} finding(s)",
            }
        ],
        "disclaimer": "Simulated review. It supports, but does not replace, expert peer review.",
    }
