"""Async GitHub REST API client with rate-limit handling and retries."""

import asyncio
import base64
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

GITHUB_API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: Optional[str] = None, timeout: float = 30.0) -> None:
        self.token = token if token is not None else (os.getenv("GITHUB_TOKEN") or None)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git-repo-evaluator/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(
        self,
        path: str,
        params: Optional[dict] = None,
        max_retries: int = 3,
        tolerate: tuple[int, ...] = (),
    ) -> Any:
        for attempt in range(max_retries):
            r = await self._client.get(path, params=params)
            if r.status_code in tolerate:
                return None
            if r.status_code == 200:
                return r.json()
            remaining = r.headers.get("x-ratelimit-remaining")
            if r.status_code == 403 and remaining == "0":
                reset = int(r.headers.get("x-ratelimit-reset", "0"))
                wait = max(reset - int(datetime.now(tz=timezone.utc).timestamp()), 1)
                if wait > 120:
                    hint = "" if self.token else " Set GITHUB_TOKEN to raise the limit."
                    raise GitHubError(
                        f"GitHub rate limit exhausted; resets in {wait}s.{hint}"
                    )
                await asyncio.sleep(wait + 1)
                continue
            if r.status_code in (502, 503, 504):
                await asyncio.sleep(2**attempt)
                continue
            r.raise_for_status()
        raise GitHubError(f"Exceeded retries for {path}")

    async def get_repo(self, owner: str, repo: str) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}")
        if data is None:
            raise GitHubError(f"Repo not found: {owner}/{repo}")
        return data

    async def list_commits(self, owner: str, repo: str, since: Optional[str] = None) -> list:
        params: dict = {"per_page": 100}
        if since:
            params["since"] = since
        return (
            await self._get(
                f"/repos/{owner}/{repo}/commits", params=params, tolerate=(404, 409)
            )
            or []
        )

    async def list_contributors(self, owner: str, repo: str) -> list:
        return (
            await self._get(
                f"/repos/{owner}/{repo}/contributors",
                params={"per_page": 100, "anon": "true"},
                tolerate=(204, 404),
            )
            or []
        )

    async def list_releases(self, owner: str, repo: str) -> list:
        return (
            await self._get(
                f"/repos/{owner}/{repo}/releases",
                params={"per_page": 10},
                tolerate=(404,),
            )
            or []
        )

    async def list_closed_pulls(self, owner: str, repo: str) -> list:
        return (
            await self._get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "closed", "per_page": 50},
                tolerate=(404,),
            )
            or []
        )

    async def get_tree(self, owner: str, repo: str, branch: str) -> list[dict]:
        data = await self._get(
            f"/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
            tolerate=(404, 409),
        )
        if not data:
            return []
        return data.get("tree", [])

    async def get_readme(self, owner: str, repo: str) -> Optional[str]:
        data = await self._get(f"/repos/{owner}/{repo}/readme", tolerate=(404,))
        if not data:
            return None
        try:
            return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except Exception:
            return None

    async def get_file_content(
        self, owner: str, repo: str, path: str, max_bytes: int = 200_000
    ) -> Optional[str]:
        """Fetch a single file's text content. Returns None for dirs, binaries, or >max_bytes."""
        data = await self._get(
            f"/repos/{owner}/{repo}/contents/{path}", tolerate=(404, 403)
        )
        if not data or isinstance(data, list):
            return None
        if data.get("encoding") != "base64":
            return None
        if data.get("size", 0) > max_bytes:
            return None
        try:
            raw = base64.b64decode(data.get("content", ""))
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None
