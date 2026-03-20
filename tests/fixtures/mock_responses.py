"""Canned API response dicts and factory functions for tests."""

from typing import Any, Dict, List


def make_repo(name: str, private: bool = False) -> Dict[str, Any]:
    """Return a minimal repository metadata dict."""
    return {
        "id": hash(name) & 0xFFFFFF,
        "name": name,
        "full_name": f"test-org/{name}",
        "private": private,
        "clone_url": f"https://github.com/test-org/{name}.git",
        "html_url": f"https://github.com/test-org/{name}",
        "default_branch": "main",
        "description": f"Repository {name}",
    }


def make_issue(number: int, title: str, state: str = "open") -> Dict[str, Any]:
    """Return a minimal issue metadata dict."""
    return {
        "id": number,
        "number": number,
        "title": title,
        "state": state,
        "body": "",
        "user": make_user("test-user"),
        "labels": [],
        "comments": 0,
    }


def make_pr(number: int, title: str, state: str = "open") -> Dict[str, Any]:
    """Return a minimal pull request metadata dict."""
    return {
        "id": number,
        "number": number,
        "title": title,
        "state": state,
        "body": "",
        "user": make_user("test-user"),
        "head": {"ref": "feature-branch", "sha": "abc123"},
        "base": {"ref": "main", "sha": "def456"},
        "pull_request": {"url": f"https://api.github.com/repos/test-org/repo/pulls/{number}"},
    }


def make_release(tag_name: str, name: str) -> Dict[str, Any]:
    """Return a minimal release metadata dict."""
    return {
        "id": hash(tag_name) & 0xFFFFFF,
        "tag_name": tag_name,
        "name": name,
        "body": "",
        "draft": False,
        "prerelease": False,
        "assets": [],
    }


def make_user(login: str) -> Dict[str, Any]:
    """Return a minimal user metadata dict."""
    return {
        "id": hash(login) & 0xFFFFFF,
        "login": login,
        "type": "User",
        "site_admin": False,
    }


SAMPLE_ORG_RESPONSE: Dict[str, Any] = {
    "id": 1,
    "login": "test-org",
    "name": "Test Organisation",
    "description": "A test organisation",
    "public_repos": 2,
    "total_private_repos": 0,
    "owned_private_repos": 0,
    "plan": {"name": "free"},
}

SAMPLE_REPOS_RESPONSE: List[Dict[str, Any]] = [
    make_repo("repo-alpha"),
    make_repo("repo-beta", private=True),
]

SAMPLE_ISSUES_RESPONSE: List[Dict[str, Any]] = [
    make_issue(1, "First issue"),
    make_issue(2, "Second issue", state="closed"),
]

SAMPLE_PRS_RESPONSE: List[Dict[str, Any]] = [
    make_pr(10, "Add feature X"),
]
