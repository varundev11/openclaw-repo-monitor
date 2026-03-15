import os
from collector import MonitorCollector

def test_missing_token(monkeypatch):
    monkeypatch.delenv('GIST_TOKEN', raising=False)
    try:
        MonitorCollector()
        assert False, "should have raised"
    except RuntimeError:
        assert True


def test_summarize_snapshot_prioritizes_issues():
    collector = MonitorCollector.__new__(MonitorCollector)

    snap = {
        "fetched_at": "2026-03-15T00:00:00Z",
        "repo": {"full_name": "openclaw/openclaw"},
        "issues": [
            {
                "number": i,
                "title": f"Issue {i}",
                "updated_at": f"2026-03-15T00:{i:02d}:00Z",
                "related_prs": [{"number": i + 100}] if i % 2 == 0 else [],
                "comments": [{"body": "full comment"}],
                "timeline": [{"event": "commented"}],
                "body": "full issue body",
                "labels": ["bug"],
            }
            for i in range(1, 13)
        ],
        "prs": [
            {
                "number": i,
                "title": f"PR {i}",
                "updated_at": f"2026-03-15T01:{i:02d}:00Z",
                "user": "contributor",
                "mergeable_state": "clean",
                "labels": ["enhancement"],
                "comments_count": 1,
                "review_comments_count": 1,
                "issue_comments": [{"body": "comment"}],
                "review_comments": [{"body": "review"}],
                "timeline": [{"event": "review_requested"}],
                "linked_issue_numbers": [i],
                "body": "full pr body",
                "state": "open",
                "html_url": "https://example.com/pr",
            }
            for i in range(1, 11)
        ],
    }

    report = collector.summarize_snapshot(snap)

    assert report["focus"] == "issues"
    assert len(report["top_issues"]) == 12
    assert len(report["top_prs"]) == 5
    assert report["issue_focus_summary"]["reported_issues"] == 12
    assert report["issue_focus_summary"]["reported_prs"] == 5
    assert report["issue_focus_summary"]["issues_with_related_prs"] == 6


def test_load_latest_skips_empty_or_invalid_snapshot():
    collector = MonitorCollector.__new__(MonitorCollector)

    class DummyGist:
        files = {
            "snapshot_20260315T180000Z.json": object(),
            "snapshot_20260315T170000Z.json": object(),
        }

    collector.gist = DummyGist()

    contents = {
        "snapshot_20260315T180000Z.json": "",
        "snapshot_20260315T170000Z.json": '{"ok": true}',
    }

    collector._get_gist_file_content = lambda filename: contents.get(filename)

    snap = collector.load_latest()
    assert snap == {"ok": True}
