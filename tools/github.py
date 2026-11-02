import os
import base64
import httpx
from dotenv import load_dotenv

load_dotenv()


def _get_headers():
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GH_TOKEN", "")
    ).strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_list_repos(max_results: int = 10) -> list:
    """List the authenticated user's GitHub repositories with details."""
    headers = _get_headers()
    if "Authorization" not in headers:
        return [{"error": "GITHUB_TOKEN not configured."}]

    try:
        r = httpx.get(
            "https://api.github.com/user/repos",
            headers=headers,
            params={"per_page": max_results, "sort": "updated"},
            timeout=15,
        )
        if r.status_code == 200:
            repos = r.json()
            if not repos:
                return [{"message": "No repositories found."}]
            return [
                {
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "description": repo.get("description") or "No description",
                    "language": repo.get("language") or "Unknown",
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo.get("html_url"),
                    "updated_at": repo.get("updated_at"),
                }
                for repo in repos[:max_results]
            ]
        return [{"error": f"GitHub API error ({r.status_code}): {r.text}"}]
    except Exception as e:
        return [{"error": f"Failed to list GitHub repositories: {e}"}]


def github_get_repo(repo_name: str) -> dict:
    """Get metadata, description, and status for a specific repository (e.g. 'sayan-does/tashubot' or 'tashubot')."""
    headers = _get_headers()
    if "Authorization" not in headers:
        return {"error": "GITHUB_TOKEN not configured."}

    full_name = repo_name.strip()
    if "/" not in full_name:
        # Prepend authenticated username or sayan-does
        full_name = f"sayan-does/{full_name}"

    try:
        r = httpx.get(
            f"https://api.github.com/repos/{full_name}",
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            return {
                "name": data.get("name"),
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "default_branch": data.get("default_branch"),
                "language": data.get("language"),
                "stars": data.get("stargazers_count"),
                "forks": data.get("forks_count"),
                "open_issues": data.get("open_issues_count"),
                "url": data.get("html_url"),
            }
        return {"error": f"Repository '{repo_name}' not found ({r.status_code}): {r.text}"}
    except Exception as e:
        return {"error": f"Error fetching repository info: {e}"}


def github_read_file(repo_name: str, file_path: str, branch: str = "main") -> dict:
    """Read code or file content from a GitHub repository."""
    headers = _get_headers()
    if "Authorization" not in headers:
        return {"error": "GITHUB_TOKEN not configured."}

    full_name = repo_name.strip()
    if "/" not in full_name:
        full_name = f"sayan-does/{full_name}"

    clean_path = file_path.strip().lstrip("/")

    try:
        r = httpx.get(
            f"https://api.github.com/repos/{full_name}/contents/{clean_path}",
            headers=headers,
            params={"ref": branch},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            encoded = data.get("content", "")
            raw = base64.b64decode(encoded).decode("utf-8", errors="replace")
            return {
                "file_path": clean_path,
                "repo": full_name,
                "content": raw[:3500],
                "truncated": len(raw) > 3500,
            }
        return {"error": f"Could not read file '{clean_path}' in '{full_name}' ({r.status_code})"}
    except Exception as e:
        return {"error": f"Error reading file from GitHub: {e}"}


def github_list_files(repo_name: str, path: str = "", branch: str = "main") -> list:
    """List files and folders in a GitHub repository directory or root."""
    headers = _get_headers()
    if "Authorization" not in headers:
        return [{"error": "GITHUB_TOKEN not configured."}]

    full_name = repo_name.strip()
    if "/" not in full_name:
        full_name = f"sayan-does/{full_name}"

    clean_path = path.strip().lstrip("/")
    endpoint = (
        f"https://api.github.com/repos/{full_name}/contents/{clean_path}"
        if clean_path
        else f"https://api.github.com/repos/{full_name}/contents"
    )

    try:
        r = httpx.get(
            endpoint,
            headers=headers,
            params={"ref": branch},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return [
                    {
                        "name": item.get("name"),
                        "path": item.get("path"),
                        "type": item.get("type"),
                        "size": item.get("size", 0),
                    }
                    for item in data
                ]
            elif isinstance(data, dict):
                return [{"name": data.get("name"), "path": data.get("path"), "type": data.get("type", "file")}]
        return [{"error": f"Could not list contents for '{clean_path}' in '{full_name}' ({r.status_code})"}]
    except Exception as e:
        return [{"error": f"Error listing repository contents: {e}"}]


def github_get_profile(username: str = None) -> dict:
    """Fetch GitHub profile information and statistics."""
    headers = _get_headers()
    target_url = f"https://api.github.com/users/{username}" if username else "https://api.github.com/user"

    try:
        r = httpx.get(target_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {
                "username": data.get("login"),
                "name": data.get("name"),
                "bio": data.get("bio"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "url": data.get("html_url"),
            }
        return {"error": f"GitHub user error ({r.status_code}): {r.text}"}
    except Exception as e:
        return {"error": f"Failed to get GitHub profile: {e}"}
