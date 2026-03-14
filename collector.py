import os
import json
import asyncio
from datetime import datetime
from github import Github, InputFileContent

class MonitorCollector:
    def __init__(self, owner: str = "openclaw", repo: str = "openclaw"):
        self.owner = owner
        self.repo = repo
        token = os.getenv("GIST_TOKEN")
        self.gh = Github(token) if token else Github()
        self.gist_description = "openclaw-repo-monitor snapshots"
        self.gist = self._get_or_create_gist()
        self._lock = asyncio.Lock()

    def _get_or_create_gist(self):
        token = os.getenv("GIST_TOKEN")
        if not token:
            raise RuntimeError("GIST_TOKEN required for creating/updating gists")
        user = self.gh.get_user()
        gists = user.get_gists()
        for g in gists:
            if g.description == self.gist_description:
                return g
        # create new secret gist
        return user.create_gist(
            public=False, 
            description=self.gist_description, 
            files={"README.md": InputFileContent("Initial gist content for openclaw-repo-monitor snapshots")}
        )

    def list_snapshots(self):
        files = [f for f in self.gist.files.keys() if f.startswith("snapshot_") and f.endswith(".json")]
        files.sort(reverse=True)
        return files

    def load_latest(self):
        files = self.list_snapshots()
        if not files:
            return None
        content = self.gist.files[files[0]].content
        return json.loads(content)

    async def schedule_loop(self, interval_minutes: int = 30):
        while True:
            try:
                await self.collect_and_prune()
            except Exception as e:
                print("snapshot error:", e)
            await asyncio.sleep(interval_minutes * 60)

    async def collect_and_prune(self):
        async with self._lock:
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            snap = self.collect_snapshot()
            # update gist with new snapshot, keep latest 3
            current_files = dict(self.gist.files)
            new_filename = f"snapshot_{ts}.json"
            new_files = {new_filename: InputFileContent(json.dumps(snap, indent=2))}
            # add existing latest 2
            existing_snapshots = sorted([f for f in current_files.keys() if f.startswith("snapshot_") and f.endswith(".json")], reverse=True)
            for f in existing_snapshots[:2]:
                new_files[f] = InputFileContent(current_files[f].content)
            self.gist.edit(files=new_files)

    def get_snapshot_content(self, ts: str):
        filename = f"snapshot_{ts}.json"
        if filename not in self.gist.files:
            return None
        return self.gist.files[filename].content

    def collect_snapshot(self):
        repo = self.gh.get_repo(f"{self.owner}/{self.repo}")
        snapshot = {
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "repo": {
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "stargazers_count": repo.stargazers_count,
                "open_issues_count": repo.open_issues_count,
            },
            "prs": [],
            "issues": [],
            "recent_commits": []
        }
        # pull recent PRs (open + last 50)
        pulls = repo.get_pulls(state='open', sort='updated', direction='desc')
        for pr in pulls[:50]:
            snapshot['prs'].append(self._compact_pr(pr))
        # issues (open recent)
        issues = repo.get_issues(state='open', sort='updated', direction='desc')
        for issue in issues[:50]:
            if issue.pull_request:
                continue
            snapshot['issues'].append(self._compact_issue(issue))
        # recent commits on default branch
        commits = repo.get_commits(sha=repo.default_branch)
        for c in commits[:20]:
            snapshot['recent_commits'].append({
                'sha': c.sha,
                'message': c.commit.message.split('\n')[0],
                'author': (c.author.login if c.author else c.commit.author.name),
                'date': c.commit.author.date.isoformat()
            })
        return snapshot

    def _compact_pr(self, pr):
        # minimal useful fields
        return {
            'number': pr.number,
            'title': pr.title,
            'user': pr.user.login if pr.user else None,
            'created_at': pr.created_at.isoformat() if pr.created_at else None,
            'updated_at': pr.updated_at.isoformat() if pr.updated_at else None,
            'merged': pr.is_merged(),
            'merged_at': pr.merged_at.isoformat() if pr.merged_at else None,
            'mergeable_state': pr.mergeable_state,
            'labels': [l.name for l in pr.labels],
            'requested_reviewers': [r.login for r in pr.get_review_requests()[0]],
            'assignees': [a.login for a in pr.assignees],
            'comments_count': pr.comments,
            'review_comments_count': pr.review_comments,
            'last_comment_excerpt': self._last_comment_excerpt_pr(pr),
            'commits_count': pr.commits
        }

    def _last_comment_excerpt_pr(self, pr):
        try:
            comments = pr.get_issue_comments()
            if comments.totalCount == 0:
                return None
            last = comments.reversed[0]
            text = last.body or ""
            return text[:300]
        except Exception:
            return None

    def _compact_issue(self, issue):
        return {
            'number': issue.number,
            'title': issue.title,
            'user': issue.user.login if issue.user else None,
            'created_at': issue.created_at.isoformat() if issue.created_at else None,
            'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
            'labels': [l.name for l in issue.labels],
            'comments_count': issue.comments,
            'last_comment_excerpt': self._last_comment_excerpt_issue(issue)
        }

    def _last_comment_excerpt_issue(self, issue):
        try:
            comments = issue.get_comments()
            if comments.totalCount == 0:
                return None
            last = comments.reversed[0]
            return (last.body or "")[:300]
        except Exception:
            return None

    def summarize_snapshot(self, snap):
        # produce compact report similar to earlier memory reports
        report = {
            'fetched_at': snap.get('fetched_at'),
            'repo': snap.get('repo'),
            'top_prs': [],
            'top_issues': []
        }
        # top PRs by updated_at
        prs = sorted(snap.get('prs', []), key=lambda p: p.get('updated_at') or '', reverse=True)[:10]
        for p in prs:
            report['top_prs'].append({
                'number': p['number'],
                'title': p['title'],
                'user': p['user'],
                'updated_at': p['updated_at'],
                'mergeable_state': p['mergeable_state'],
                'labels': p['labels'],
                'comments_count': p['comments_count'],
                'last_comment_excerpt': p['last_comment_excerpt']
            })
        issues = sorted(snap.get('issues', []), key=lambda i: i.get('updated_at') or '', reverse=True)[:10]
        for it in issues:
            report['top_issues'].append(it)
        return report
