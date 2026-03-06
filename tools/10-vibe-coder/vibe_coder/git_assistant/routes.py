"""GitAssistant FastAPI routes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
router = APIRouter(tags=["GitAssistant"])


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "git-assistant", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["git_assistant"]


def _mona(request: Request) -> Path:
    return request.app.state.db_paths["mona_events"]


# -- Request models --------------------------------------------------------


class PRDescriptionRequest(BaseModel):
    repo_path: str
    base_branch: str = "main"
    head_branch: str = ""


class ReviewerRequest(BaseModel):
    repo_path: str
    base_branch: str = "main"
    head_branch: str = ""
    count: int = 3


class ReleaseNotesRequest(BaseModel):
    repo_path: str
    from_tag: str
    to_tag: str = "HEAD"


class LabelIssueRequest(BaseModel):
    owner: str
    repo: str
    issue_number: int
    token: str = ""


class ImproveCommitRequest(BaseModel):
    repo_path: str
    message: str
    base_branch: str = "main"
    head_branch: str = ""


class BranchSummaryRequest(BaseModel):
    repo_path: str
    base_branch: str = "main"
    head_branch: str = ""


# -- Page ------------------------------------------------------------------


@router.get("/git-assistant/", response_class=HTMLResponse)
async def git_assistant_page(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        repos = [dict(r) for r in conn.execute(
            "SELECT * FROM repositories ORDER BY last_analyzed DESC"
        ).fetchall()]
        recent_prs = [dict(r) for r in conn.execute(
            "SELECT pg.*, r.github_repo FROM pr_generations pg "
            "LEFT JOIN repositories r ON pg.repo_id = r.id "
            "ORDER BY pg.created_at DESC LIMIT 10"
        ).fetchall()]
        recent_releases = [dict(r) for r in conn.execute(
            "SELECT rn.*, r.github_repo FROM release_notes rn "
            "LEFT JOIN repositories r ON rn.repo_id = r.id "
            "ORDER BY rn.generated_at DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "git_assistant/index.html",
        _ctx(request, repos=repos, recent_prs=recent_prs, recent_releases=recent_releases),
    )


# -- PR Description --------------------------------------------------------


@router.post("/api/git-assistant/pr-description")
async def generate_pr_description(request: Request, body: PRDescriptionRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.pr.diff_analyzer import DiffAnalyzer
    from vibe_coder.git_assistant.pr.description_generator import PRDescriptionGenerator

    llm = request.app.state.llm
    head = body.head_branch or _current_branch(body.repo_path)

    try:
        analyzer = DiffAnalyzer()
        diff_summary = analyzer.analyze(body.repo_path, body.base_branch, head)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    generator = PRDescriptionGenerator()
    pr_desc = await generator.generate(diff_summary, llm)

    db = _db(request)
    repo_id = _ensure_repo(db, body.repo_path)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO pr_generations "
            "(repo_id, branch_name, base_branch, diff_summary, generated_title, generated_body, "
            "files_changed, insertions, deletions) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                repo_id, head, body.base_branch,
                json.dumps([{"path": f.path, "type": f.change_type} for f in diff_summary.file_summaries]),
                pr_desc.title, pr_desc.body,
                diff_summary.files_changed, diff_summary.insertions, diff_summary.deletions,
            ),
        )

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="git-assistant",
        summary=f"PR description generated for {head} -> {body.base_branch}",
    )

    return {
        "title": pr_desc.title,
        "body": pr_desc.body,
        "diff": {
            "files_changed": diff_summary.files_changed,
            "insertions": diff_summary.insertions,
            "deletions": diff_summary.deletions,
        },
    }


# -- Reviewers -------------------------------------------------------------


@router.post("/api/git-assistant/reviewers")
async def suggest_reviewers(request: Request, body: ReviewerRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.pr.diff_analyzer import DiffAnalyzer
    from vibe_coder.git_assistant.pr.reviewer_suggester import ReviewerSuggester

    head = body.head_branch or _current_branch(body.repo_path)

    try:
        analyzer = DiffAnalyzer()
        diff_summary = analyzer.analyze(body.repo_path, body.base_branch, head)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    changed_files = [f.path for f in diff_summary.file_summaries]
    suggester = ReviewerSuggester()
    suggestions = suggester.suggest(body.repo_path, changed_files, count=body.count)

    return {
        "reviewers": [
            {"email": s.email, "score": s.score, "files_owned": s.files_owned}
            for s in suggestions
        ],
    }


# -- Release Notes ---------------------------------------------------------


@router.post("/api/git-assistant/release-notes")
async def generate_release_notes(request: Request, body: ReleaseNotesRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.release.commit_analyzer import CommitAnalyzer
    from vibe_coder.git_assistant.release.notes_generator import ReleaseNotesGenerator
    from vibe_coder.git_assistant.release.version_helper import VersionHelper

    llm = request.app.state.llm

    try:
        commits = _commits_between(body.repo_path, body.from_tag, body.to_tag)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analyzer = CommitAnalyzer()
    categorized = analyzer.categorize(commits)

    helper = VersionHelper()
    try:
        suggested_version = helper.suggest_version(body.from_tag, categorized)
    except ValueError:
        suggested_version = body.to_tag

    generator = ReleaseNotesGenerator()
    notes = await generator.generate(categorized, suggested_version, llm)

    db = _db(request)
    repo_id = _ensure_repo(db, body.repo_path)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO release_notes "
            "(repo_id, from_tag, to_tag, version, notes_content, commit_count, features, fixes, breaking) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                repo_id, body.from_tag, body.to_tag, suggested_version, notes,
                len(commits),
                json.dumps([c.description for c in categorized.features]),
                json.dumps([c.description for c in categorized.fixes]),
                json.dumps([c.description for c in categorized.breaking]),
            ),
        )

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="git-assistant",
        summary=f"Release notes generated for {body.from_tag}..{body.to_tag}",
    )

    return {
        "version": suggested_version,
        "notes": notes,
        "commit_count": len(commits),
    }


# -- Label Issue -----------------------------------------------------------


@router.post("/api/git-assistant/label-issue")
async def label_issue(request: Request, body: LabelIssueRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.issues.issue_fetcher import IssueFetcher
    from vibe_coder.git_assistant.issues.label_taxonomy import LabelTaxonomy
    from vibe_coder.git_assistant.issues.auto_labeler import AutoLabeler

    llm = request.app.state.llm
    token = body.token or _get_gh_token(request)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token required")

    fetcher = IssueFetcher()
    taxonomy = LabelTaxonomy()
    labeler = AutoLabeler()

    issues = await fetcher.fetch_open_issues(body.owner, body.repo, token)
    target = next((i for i in issues if i.number == body.issue_number), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Issue #{body.issue_number} not found in open issues")

    available_labels = await taxonomy.fetch_labels(body.owner, body.repo, token)
    suggestions = await labeler.suggest_labels(target, available_labels, llm)

    db = _db(request)
    repo_id = _ensure_repo_github(db, body.owner, body.repo)
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO issue_labels (repo_id, issue_number, suggested_labels, confidence_scores) "
            "VALUES (?,?,?,?)",
            (
                repo_id,
                body.issue_number,
                json.dumps([s.name for s in suggestions]),
                json.dumps([s.confidence for s in suggestions]),
            ),
        )

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="git-assistant",
        summary=f"Labels suggested for {body.owner}/{body.repo}#{body.issue_number}",
    )

    return {
        "issue_number": body.issue_number,
        "suggestions": [
            {"name": s.name, "confidence": s.confidence} for s in suggestions
        ],
    }


# -- Improve Commit --------------------------------------------------------


@router.post("/api/git-assistant/improve-commit")
async def improve_commit(request: Request, body: ImproveCommitRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.pr.diff_analyzer import DiffAnalyzer
    from vibe_coder.git_assistant.commits.message_improver import CommitMessageImprover

    llm = request.app.state.llm
    head = body.head_branch or _current_branch(body.repo_path)

    try:
        analyzer = DiffAnalyzer()
        diff_summary = analyzer.analyze(body.repo_path, body.base_branch, head)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    improver = CommitMessageImprover()
    improved = await improver.improve(body.message, diff_summary, llm)

    return {"original": body.message, "improved": improved}


# -- Branch Summary --------------------------------------------------------


@router.post("/api/git-assistant/branch-summary")
async def branch_summary(request: Request, body: BranchSummaryRequest) -> dict[str, Any]:
    from vibe_coder.git_assistant.pr.diff_analyzer import DiffAnalyzer
    from vibe_coder.git_assistant.release.commit_analyzer import CommitAnalyzer

    head = body.head_branch or _current_branch(body.repo_path)

    try:
        analyzer = DiffAnalyzer()
        diff_summary = analyzer.analyze(body.repo_path, body.base_branch, head)
        commits = _commits_between(body.repo_path, body.base_branch, head)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    commit_analyzer = CommitAnalyzer()
    categorized = commit_analyzer.categorize(commits)

    return {
        "branch": head,
        "base": body.base_branch,
        "diff": {
            "files_changed": diff_summary.files_changed,
            "insertions": diff_summary.insertions,
            "deletions": diff_summary.deletions,
            "truncated": diff_summary.truncated,
        },
        "commits": {
            "total": len(commits),
            "features": len(categorized.features),
            "fixes": len(categorized.fixes),
            "breaking": len(categorized.breaking),
            "improvements": len(categorized.improvements),
            "other": len(categorized.other),
        },
        "files": [
            {"path": f.path, "insertions": f.insertions, "deletions": f.deletions, "type": f.change_type}
            for f in diff_summary.file_summaries[:20]
        ],
    }


# -- Repos -----------------------------------------------------------------


@router.get("/api/git-assistant/repos")
async def list_repos(request: Request) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        repos = [dict(r) for r in conn.execute(
            "SELECT * FROM repositories ORDER BY last_analyzed DESC"
        ).fetchall()]
    return {"repos": repos}


# -- Helpers ---------------------------------------------------------------


def _current_branch(repo_path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cannot determine current branch: {result.stderr.strip()}")
    return result.stdout.strip()


def _commits_between(repo_path: str, from_ref: str, to_ref: str) -> list[dict[str, str]]:
    result = subprocess.run(
        ["git", "log", "--format=%H|||%s|||%b|||END", f"{from_ref}..{to_ref}"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")

    commits: list[dict[str, str]] = []
    for entry in result.stdout.split("|||END"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("|||", 2)
        if len(parts) < 2:
            continue
        sha = parts[0].strip()
        subject = parts[1].strip()
        body = parts[2].strip() if len(parts) > 2 else ""
        message = f"{subject}\n\n{body}".strip() if body else subject
        commits.append({"hash": sha, "message": message})

    return commits


def _ensure_repo(db: Path, repo_path: str) -> int:
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE repo_path = ?", (repo_path,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE repositories SET last_analyzed = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            return row["id"]
        cursor = conn.execute(
            "INSERT INTO repositories (repo_path, last_analyzed) VALUES (?, CURRENT_TIMESTAMP)",
            (repo_path,),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def _ensure_repo_github(db: Path, owner: str, repo: str) -> int:
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT id FROM repositories WHERE github_owner = ? AND github_repo = ?",
            (owner, repo),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE repositories SET last_analyzed = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],),
            )
            return row["id"]
        cursor = conn.execute(
            "INSERT INTO repositories (github_owner, github_repo, github_remote, last_analyzed) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (owner, repo, f"https://github.com/{owner}/{repo}", ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def _get_gh_token(request: Request) -> str:
    config = request.app.state.config
    source = getattr(config.extra, "github_token_source", None) or config.extra.get("github_token_source", "gh_auth")
    if source == "gh_auth":
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return ""
