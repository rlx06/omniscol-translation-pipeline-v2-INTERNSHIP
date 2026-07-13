import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.export import render_summary_markdown
from src.models import ValidationIssue


def test_summary_perfect_score_when_no_issues():
    summary = render_summary_markdown([], "pl", "webapp", total_keys=100, missing_keys=0)
    assert "Overall score: 100%" in summary
    assert "Total keys**: 100" in summary


def test_summary_penalizes_blockers_more_than_warnings():
    blockers = [ValidationIssue("k1", "BLOCKER", "msg", "structural")]
    warnings = [ValidationIssue("k2", "WARNING", "msg", "structural")]

    score_with_blocker = render_summary_markdown(blockers, "pl", "webapp", 100, 0)
    score_with_warning = render_summary_markdown(warnings, "pl", "webapp", 100, 0)

    def extract_score(text):
        line = [l for l in text.splitlines() if "Overall score" in l][0]
        return float(line.split(":")[1].strip().rstrip("%"))

    assert extract_score(score_with_blocker) < extract_score(score_with_warning)


def test_summary_score_never_negative():
    many_blockers = [ValidationIssue(f"k{i}", "BLOCKER", "msg", "structural") for i in range(50)]
    summary = render_summary_markdown(many_blockers, "pl", "webapp", total_keys=10, missing_keys=0)

    def extract_score(text):
        line = [l for l in text.splitlines() if "Overall score" in l][0]
        return float(line.split(":")[1].strip().rstrip("%"))

    assert extract_score(summary) == 0.0


def test_summary_breaks_down_by_stage():
    issues = [
        ValidationIssue("k1", "ERROR", "msg", "semantic"),
        ValidationIssue("k2", "ERROR", "msg", "canonical"),
        ValidationIssue("k3", "WARNING", "msg", "structural"),
    ]
    summary = render_summary_markdown(issues, "pl", "webapp", 100, 0)
    assert "Semantic flags" in summary and ": 1" in summary
    assert "Canonical label flags**: 1" in summary
    assert "Structural flags" in summary and "1" in summary
