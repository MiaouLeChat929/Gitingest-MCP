import re
import asyncio
import httpx
import logging
import zipfile
import io
import fnmatch
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('gitingest-mcp')

class GitIngester:
    def __init__(self, url: str, branch: Optional[str] = None):
        """Initialize the GitIngester with a repository URL."""
        self.url: str = url
        self.branch: Optional[str] = branch

        # Parse the GitHub URL to get owner and repo
        match = re.search(r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?", self.url)
        if match:
            self.owner, self.repo, url_branch = match.groups()
            if url_branch and not self.branch:
                self.branch = url_branch
        else:
            self.owner = ""
            self.repo = ""

        if not self.branch:
            self.branch = "main" # Default, though we might want to check the default branch

        self.summary: Optional[Dict[str, Any]] = None
        self.tree: Optional[str] = None
        self.files_content: Dict[str, str] = {}

        self._fetched_from_api = False
        self._fetched_from_zip = False

    async def fetch_repo_data(self) -> None:
        """Asynchronously fetch and process repository data. Try efficient API first, then ZIP if rate limited."""
        if not self.owner or not self.repo:
            self._set_fallback_summary("Invalid GitHub URL")
            return

        try:
            # 1. Try to fetch the tree using the GitHub REST API (fastest if not rate limited)
            success = await self._fetch_via_api()
            if success:
                self._fetched_from_api = True
                return
        except Exception as e:
            logger.warning(f"Failed to fetch via API: {e}")

        # 2. Fallback to downloading the ZIP archive
        try:
            success = await self._fetch_via_zip()
            if success:
                self._fetched_from_zip = True
                return
        except Exception as e:
            logger.error(f"Failed to fetch via ZIP: {e}")
            self._set_fallback_summary(f"Failed to fetch repository: {str(e)}")

    def _set_fallback_summary(self, reason: str):
        self.summary = {
            "repository": f"{self.owner}/{self.repo}" if self.owner else self.url,
            "num_files": None,
            "token_count": "",
            "raw": f"Repository: {self.owner}/{self.repo}\n(Status: {reason})"
        }
        self.tree = f"Directory structure unavailable. Reason: {reason}"

    async def _fetch_via_api(self) -> bool:
        """Fetch repository tree via GitHub REST API."""
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/trees/{self.branch}?recursive=1"

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, follow_redirects=True, headers={"Accept": "application/vnd.github.v3+json"})

            if response.status_code == 404:
                # Might be a different default branch, try 'master' if 'main' fails
                if self.branch == 'main':
                    self.branch = 'master'
                    api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/git/trees/{self.branch}?recursive=1"
                    response = await client.get(api_url, follow_redirects=True, headers={"Accept": "application/vnd.github.v3+json"})

            if response.status_code != 200:
                return False

            data = response.json()
            if "tree" not in data:
                return False

            # Build tree representation
            tree_lines = []
            file_count = 0
            for item in data["tree"]:
                path = item["path"]
                if item["type"] == "tree":
                    tree_lines.append(f"{path}/")
                else:
                    tree_lines.append(path)
                    file_count += 1

            self.tree = "\n".join(sorted(tree_lines))

            self.summary = {
                "repository": f"{self.owner}/{self.repo}",
                "num_files": file_count,
                "token_count": "Unknown (API mode)",
                "raw": f"Repository: {self.owner}/{self.repo}\nFiles analyzed: {file_count}\nEstimated tokens: Unknown"
            }
            return True

    async def _fetch_via_zip(self) -> bool:
        """Download and extract the repository ZIP file."""
        zip_url = f"https://github.com/{self.owner}/{self.repo}/archive/refs/heads/{self.branch}.zip"

        async with httpx.AsyncClient() as client:
            response = await client.get(zip_url, follow_redirects=True)

            if response.status_code == 404 and self.branch == 'main':
                self.branch = 'master'
                zip_url = f"https://github.com/{self.owner}/{self.repo}/archive/refs/heads/{self.branch}.zip"
                response = await client.get(zip_url, follow_redirects=True)

            if response.status_code != 200:
                return False

            # Read zip file from memory
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                    # Find the root directory name in the zip (usually repo-branch/)
                    file_list = zip_ref.namelist()
                    if not file_list:
                        return False

                    root_dir = file_list[0].split('/')[0] + '/'

                    tree_lines = []
                    file_count = 0
                    total_chars = 0

                    for zip_info in zip_ref.filelist:
                        # Skip directories and remove root_dir prefix
                        if zip_info.filename.endswith('/'):
                            # Add directory to tree, ignoring the root wrapper
                            if zip_info.filename != root_dir:
                                tree_lines.append(zip_info.filename[len(root_dir):])
                            continue

                        # It's a file
                        clean_path = zip_info.filename[len(root_dir):]
                        tree_lines.append(clean_path)
                        file_count += 1

                        # Read content to cache and count roughly for tokens
                        # We only read text files or files we can decode
                        try:
                            content_bytes = zip_ref.read(zip_info.filename)
                            content_str = content_bytes.decode('utf-8')
                            self.files_content[clean_path] = content_str
                            total_chars += len(content_str)
                        except UnicodeDecodeError:
                            # Skip binary files or non-utf-8
                            pass

                    self.tree = "\n".join(sorted(tree_lines))

                    # Rough token estimation (1 token ≈ 4 characters)
                    tokens = total_chars // 4

                    self.summary = {
                        "repository": f"{self.owner}/{self.repo}",
                        "num_files": file_count,
                        "token_count": str(tokens),
                        "raw": f"Repository: {self.owner}/{self.repo}\nFiles analyzed: {file_count}\nEstimated tokens: {tokens}"
                    }
                    return True
            except zipfile.BadZipFile:
                return False

    def get_summary(self) -> str:
        """Returns the repository summary."""
        return self.summary["raw"] if self.summary else ""

    def get_tree(self) -> Any:
        """Returns the repository tree structure."""
        return self.tree

    async def get_content(self, file_paths: Optional[List[str]] = None) -> str:
        """Returns the repository content."""
        if not file_paths:
            return "No specific files requested."

        # If we downloaded the ZIP, we have all text content in memory
        if self._fetched_from_zip:
            return self._get_files_content_from_cache(file_paths)

        # Otherwise, fetch directly via raw GitHub URLs
        return await self._fetch_raw_files(file_paths)

    def _get_files_content_from_cache(self, file_paths: List[str]) -> str:
        concatenated = ""
        for path in file_paths:
            # Handle exact match or basename match
            matched_content = None
            matched_path = None

            for cached_path, content in self.files_content.items():
                if cached_path == path or cached_path.endswith("/" + path) or path.endswith("/" + cached_path):
                    matched_content = content
                    matched_path = cached_path
                    break

            if matched_content is not None:
                if concatenated:
                    concatenated += "\n\n"
                concatenated += f"==================================================\nFile: {matched_path}\n==================================================\n{matched_content}"

        if not concatenated:
            return "Could not retrieve content for the specified files."
        return concatenated

    async def _fetch_raw_files(self, file_paths: List[str]) -> str:
        """Fallback method to fetch files directly from GitHub using raw URLs."""
        if not self.owner or not self.repo:
            return "Error: Cannot parse GitHub URL to fetch raw files."

        raw_base_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{self.branch}/"

        concatenated = ""
        async with httpx.AsyncClient() as client:
            for path in file_paths:
                clean_path = path.lstrip("/")
                url = f"{raw_base_url}{clean_path}"
                try:
                    response = await client.get(url, follow_redirects=True)
                    if response.status_code == 200:
                        content = response.text
                        if concatenated:
                            concatenated += "\n\n"
                        concatenated += f"==================================================\nFile: {path}\n==================================================\n{content}"
                    else:
                        logger.warning(f"Failed to fetch {path} via raw URL: Status {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to fetch {path} via raw URL: {e}")

        if not concatenated:
            return "Could not retrieve content for the specified files."
        return concatenated
