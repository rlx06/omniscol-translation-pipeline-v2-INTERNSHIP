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


def export_results(
    target_translations: dict[str, str],
    new_translations: dict[str, str],
    issues: list[ValidationIssue],
    output_dir: Path,
    target_lang: str,
    module: str,
) -> dict:
    """Merges new translations into the existing target file and writes the
    diff report, validation report, and review queue. Returns paths written."""
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

    save_json({"translations": merged}, final_path)

    diff_lines = [f"# Diff report - {module} ({target_lang})", "", f"Keys added/updated: {len(diff_added)}", ""]
    for key, value in diff_added.items():
        diff_lines.append(f"- `{key}`: {value!r}")
    diff_path.write_text("\n".join(diff_lines), encoding="utf-8")

    review_path.write_text(
        render_review_queue_markdown(issues, target_lang, module), encoding="utf-8"
    )

    save_json({"issues": [i.to_dict() for i in issues]}, validation_path)

    return {
        "final": str(final_path),
        "diff": str(diff_path),
        "review_queue": str(review_path),
        "validation": str(validation_path),
    }
