import os
import json
import asyncio
import re
from urllib.request import urlopen
from datetime import datetime
from zoneinfo import ZoneInfo
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
        for filename in files:
            content = self._get_gist_file_content(filename)
            if not content:
                continue
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                continue
        return None

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
            # update gist with new snapshot and keep latest 3 snapshots total
            new_filename = f"snapshot_{ts}.json"
            new_files = {new_filename: InputFileContent(json.dumps(snap, indent=2))}

            existing_snapshots = sorted(
                [f for f in self.gist.files.keys() if f.startswith("snapshot_") and f.endswith(".json")],
                reverse=True,
            )

            # delete older snapshots beyond latest 2 existing (new one makes total 3)
            for f in existing_snapshots[2:]:
                new_files[f] = None

            self.gist.edit(files=new_files)

    def get_snapshot_content(self, ts: str):
        filename = f"snapshot_{ts}.json"
        return self._get_gist_file_content(filename)

    def _get_gist_file_content(self, filename: str):
        gist_file = self.gist.files.get(filename)
        if not gist_file:
            return None

        if gist_file.content:
            return gist_file.content

        raw_url = getattr(gist_file, "raw_url", None)
        if raw_url:
            try:
                with urlopen(raw_url, timeout=20) as response:
                    return response.read().decode("utf-8")
            except Exception:
                pass

        try:
            refreshed = self.gh.get_gist(self.gist.id)
            self.gist = refreshed
            refreshed_file = refreshed.files.get(filename)
            if not refreshed_file:
                return None

            if refreshed_file.content:
                return refreshed_file.content

            refreshed_raw_url = getattr(refreshed_file, "raw_url", None)
            if refreshed_raw_url:
                with urlopen(refreshed_raw_url, timeout=20) as response:
                    return response.read().decode("utf-8")
        except Exception:
            return None

        return None

    def collect_snapshot(self):
        repo = self.gh.get_repo(f"{self.owner}/{self.repo}")
        snapshot = {
            "fetched_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
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
            snapshot['prs'].append(self._detailed_pr(pr))
        # issues (open recent)
        issues = repo.get_issues(state='open', sort='updated', direction='desc')
        for issue in issues[:50]:
            if issue.pull_request:
                continue
            snapshot['issues'].append(self._detailed_issue(issue))
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

    def _detailed_pr(self, pr):
        issue_comments = self._collect_comments(pr.get_issue_comments())
        review_comments = self._collect_comments(pr.get_comments())
        timeline = self._collect_timeline(pr.as_issue())

        return {
            'number': pr.number,
            'title': pr.title,
            'body': pr.body or "",
            'user': pr.user.login if pr.user else None,
            'created_at': pr.created_at.isoformat() if pr.created_at else None,
            'updated_at': pr.updated_at.isoformat() if pr.updated_at else None,
            'merged': pr.is_merged(),
            'merged_at': pr.merged_at.isoformat() if pr.merged_at else None,
            'state': pr.state,
            'mergeable_state': pr.mergeable_state,
            'labels': [l.name for l in pr.labels],
            'requested_reviewers': [r.login for r in pr.get_review_requests()[0]],
            'assignees': [a.login for a in pr.assignees],
            'comments_count': pr.comments,
            'review_comments_count': pr.review_comments,
            'issue_comments': issue_comments,
            'review_comments': review_comments,
            'timeline': timeline,
            'linked_issue_numbers': self._extract_issue_numbers_from_text(pr.body or ""),
            'commits_count': pr.commits,
            'html_url': pr.html_url,
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

    def _detailed_issue(self, issue):
        comments = self._collect_comments(issue.get_comments())
        timeline = self._collect_timeline(issue)

        return {
            'number': issue.number,
            'title': issue.title,
            'body': issue.body or "",
            'user': issue.user.login if issue.user else None,
            'created_at': issue.created_at.isoformat() if issue.created_at else None,
            'updated_at': issue.updated_at.isoformat() if issue.updated_at else None,
            'state': issue.state,
            'labels': [l.name for l in issue.labels],
            'comments_count': issue.comments,
            'comments': comments,
            'timeline': timeline,
            'related_prs': self._extract_related_prs_from_timeline(timeline),
            'html_url': issue.html_url,
        }

    def _collect_comments(self, comments):
        items = []
        try:
            for comment in comments:
                items.append({
                    'id': comment.id,
                    'user': comment.user.login if comment.user else None,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None,
                    'updated_at': comment.updated_at.isoformat() if comment.updated_at else None,
                    'body': comment.body or "",
                    'html_url': comment.html_url,
                })
        except Exception:
            return []
        return items

    def _collect_timeline(self, issue_like):
        items = []
        try:
            for event in issue_like.get_timeline():
                items.append({
                    'event': getattr(event, 'event', None),
                    'actor': event.actor.login if getattr(event, 'actor', None) else None,
                    'created_at': event.created_at.isoformat() if getattr(event, 'created_at', None) else None,
                    'label': event.label.name if getattr(event, 'label', None) else None,
                    'milestone': event.milestone.title if getattr(event, 'milestone', None) else None,
                    'assignee': event.assignee.login if getattr(event, 'assignee', None) else None,
                    'commit_id': getattr(event, 'commit_id', None),
                    'source': self._timeline_source(event),
                })
        except Exception:
            return []
        return items

    def _timeline_source(self, event):
        source = getattr(event, 'source', None)
        if not source:
            return None
        issue = getattr(source, 'issue', None)
        if not issue:
            return None
        return {
            'number': getattr(issue, 'number', None),
            'title': getattr(issue, 'title', None),
            'state': getattr(issue, 'state', None),
            'html_url': getattr(issue, 'html_url', None),
            'is_pull_request': bool(getattr(issue, 'pull_request', None)),
        }

    def _extract_related_prs_from_timeline(self, timeline):
        related_prs = {}
        for event in timeline:
            source = event.get('source') or {}
            if source.get('is_pull_request') and source.get('number') is not None:
                related_prs[source['number']] = {
                    'number': source.get('number'),
                    'title': source.get('title'),
                    'state': source.get('state'),
                    'html_url': source.get('html_url'),
                }
        return sorted(related_prs.values(), key=lambda p: p.get('number') or 0)

    def _extract_issue_numbers_from_text(self, text):
        issue_numbers = {int(n) for n in re.findall(r'#(\d+)', text or "")}
        return sorted(issue_numbers)

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
        # issue-first report intended for actionable contribution analysis
        report = {
            'fetched_at': snap.get('fetched_at'),
            'repo': snap.get('repo'),
            'focus': 'issues',
            'top_issues': [],
            'top_prs': [],
            'issue_focus_summary': {}
        }

        issues = sorted(snap.get('issues', []), key=lambda i: i.get('updated_at') or '', reverse=True)
        prs = sorted(snap.get('prs', []), key=lambda p: p.get('updated_at') or '', reverse=True)

        top_issues = issues[:20]
        top_prs = prs[:5]

        report['top_issues'] = top_issues
        for p in prs:
            if len(report['top_prs']) >= 5:
                break
            report['top_prs'].append({
                'number': p['number'],
                'title': p['title'],
                'body': p.get('body', ''),
                'user': p['user'],
                'updated_at': p['updated_at'],
                'state': p.get('state'),
                'mergeable_state': p['mergeable_state'],
                'labels': p['labels'],
                'linked_issue_numbers': p.get('linked_issue_numbers', []),
                'comments_count': p['comments_count'],
                'review_comments_count': p.get('review_comments_count', 0),
                'issue_comments': p.get('issue_comments', []),
                'review_comments': p.get('review_comments', []),
                'timeline': p.get('timeline', []),
                'html_url': p.get('html_url'),
            })

        report['issue_focus_summary'] = {
            'issues_in_snapshot': len(issues),
            'prs_in_snapshot': len(prs),
            'reported_issues': len(top_issues),
            'reported_prs': len(report['top_prs']),
            'issues_with_related_prs': sum(1 for i in top_issues if i.get('related_prs')),
            'issues_without_related_prs': sum(1 for i in top_issues if not i.get('related_prs')),
        }

        return report
