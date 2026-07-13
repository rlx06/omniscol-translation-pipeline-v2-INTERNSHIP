"""
Stage 10 + 11: Human review queue and export.
"""
from __future__ import annotations

from pathlib import Path

from .load import save_json
from .models import SEVERITY_ORDER, ValidationIssue


def build_review_queue(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    """Sorted by severity: BLOCKER > ERROR > WARNING > REVIEW. Human review
    should only ever need to look at this list, not the whole file."""
    return sorted(issues, key=lambda i: (SEVERITY_ORDER.get(i.severity, 99), i.key))


def render_review_queue_markdown(issues: list[ValidationIssue], target_lang: str, module: str) -> str:
    lines = [f"# Review queue - {module} ({target_lang})", ""]
    if not issues:
        lines.append("No flagged keys. Nothing requires human review.")
        return "\n".join(lines)

    counts = {}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    lines.append("## Summary")
    for severity in ("BLOCKER", "ERROR", "WARNING", "REVIEW"):
        if severity in counts:
            lines.append(f"- **{severity}**: {counts[severity]}")
    lines.append("")

    lines.append("## Flagged keys")
    for issue in build_review_queue(issues):
        lines.append(f"- **[{issue.severity}]** `{issue.key}` ({issue.stage}): {issue.message}")

    return "\n".join(lines)


def render_summary_markdown(
    issues: list[ValidationIssue],
    target_lang: str,
    module: str,
    total_keys: int,
    missing_keys: int,
) -> str:
    """
    A single, skimmable scorecard - the manager-facing counterpart to the
    detailed review queue. Requested independently by two rounds of code
    review as the easiest way for a non-technical reader to see pipeline
    health at a glance without reading a long list of individual issues.
    """
    counts = {"BLOCKER": 0, "ERROR": 0, "WARNING": 0, "REVIEW": 0}
    by_stage = {"structural": 0, "semantic": 0, "canonical": 0, "llm_review": 0}
    for issue in issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
        by_stage[issue.stage] = by_stage.get(issue.stage, 0) + 1

    # Simple scoring: blockers and errors cost the most, warnings a little,
    # reviews barely count against the score (they are low-confidence flags,
    # not confirmed problems). Score never goes below 0.
    penalty = counts["BLOCKER"] * 5 + counts["ERROR"] * 2 + counts["WARNING"] * 0.5 + counts["REVIEW"] * 0.05
    score = max(0.0, 100.0 - (penalty / max(total_keys, 1)) * 100)

    lines = [
        f"# Pipeline Summary — {module} ({target_lang})",
        "",
        f"- **Total keys**: {total_keys}",
        f"- **Missing keys**: {missing_keys}",
        f"- **Structural flags** (placeholders, HTML, punctuation, capitalization): {by_stage['structural']}",
        f"- **Semantic flags** (concept-confusion + consistency checks, all severities): {by_stage['semantic']}",
        f"- **Canonical label flags**: {by_stage['canonical']}",
        f"- **LLM review flags**: {by_stage['llm_review']}",
        "",
        f"- **BLOCKER**: {counts['BLOCKER']}",
        f"- **ERROR**: {counts['ERROR']}",
        f"- **WARNING**: {counts['WARNING']}",
        f"- **REVIEW** (low-confidence, needs a human look): {counts['REVIEW']}",
        "",
        f"## Overall score: {score:.0f}%",
        "",
        "Score is a simple weighted penalty (BLOCKER -5, ERROR -2, WARNING -0.5, "
        "REVIEW -0.05 per key affected) - it is a quick health indicator, not a "
        "certification. Always check the detailed review queue for specifics "
        "before treating a language as production-ready.",
    ]
    return "\n".join(lines)


def export_results(
    target_translations: dict[str, str],
    new_translations: dict[str, str],
    issues: list[ValidationIssue],
    output_dir: Path,
    target_lang: str,
    module: str,
    total_keys: int = 0,
    missing_keys: int = 0,
) -> dict:
    """Merges new translations into the existing target file and writes the
    diff report, validation report, review queue, and manager-facing summary.
    Returns paths written."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    merged = dict(target_translations)
    diff_added = {}
    for key, value in new_translations.items():
        if key not in merged:
            diff_added[key] = value
        merged[key] = value

    final_path = output_dir / f"{target_lang}_{module}.v2.json"
    diff_path = output_dir / f"{target_lang}_{module}.diff.md"
    review_path = output_dir / f"{target_lang}_{module}.review_queue.md"
    validation_path = output_dir / f"{target_lang}_{module}.validation.json"
    summary_path = output_dir / f"{target_lang}_{module}.summary.md"

    save_json({"translations": merged}, final_path)

    diff_lines = [f"# Diff report - {module} ({target_lang})", "", f"Keys added/updated: {len(diff_added)}", ""]
    for key, value in diff_added.items():
        diff_lines.append(f"- `{key}`: {value!r}")
    diff_path.write_text("\n".join(diff_lines), encoding="utf-8")

    review_path.write_text(
        render_review_queue_markdown(issues, target_lang, module), encoding="utf-8"
    )

    save_json({"issues": [i.to_dict() for i in issues]}, validation_path)

    summary_path.write_text(
        render_summary_markdown(issues, target_lang, module, total_keys or len(merged), missing_keys),
        encoding="utf-8",
    )

    return {

        "final": str(final_path),
        "diff": str(diff_path),
        "review_queue": str(review_path),
        "validation": str(validation_path),
        "summary": str(summary_path),
    }
