import re
import asyncio
import httpx
import logging
from gitingest import ingest
from typing import Any, Dict, List, Optional

logger = logging.getLogger('gitingest-mcp')

class GitIngester:
	def __init__(self, url: str, branch: Optional[str] = None):
		"""Initialize the GitIngester with a repository URL."""
		self.url: str = url
		self.branch: Optional[str] = branch
		if branch:
			self.url = f"{url}/tree/{branch}"
		self.summary: Optional[Dict[str, Any]] = None
		self.tree: Optional[Any] = None
		self.content: Optional[Any] = None

	async def fetch_repo_data(self) -> None:
		"""Asynchronously fetch and process repository data."""
		# Run the synchronous ingest function in a thread pool
		try:
			loop = asyncio.get_running_loop()
			summary, self.tree, self.content = await loop.run_in_executor(
				None, lambda: ingest(self.url)
			)
			self.summary = self._parse_summary(summary)
			self._is_fallback = False
		except Exception as e:
			logger.warning(f"Failed to ingest repository via gitingest: {e}. Enabling fallback mode.")
			self._is_fallback = True
			self.summary = {
				"repository": self.url.split('github.com/')[-1].split('/tree/')[0] if 'github.com' in self.url else "",
				"num_files": None,
				"token_count": "",
				"raw": f"Repository: {self.url}\n(Fallback mode active due to rate limiting/error)"
			}
			self.tree = "Directory structure unavailable in fallback mode."
			self.content = None

	def _parse_summary(self, summary_str: str) -> Dict[str, Any]:
		"""Parse the summary string into a structured dictionary."""
		summary_dict = {}

		try:
			# Extract repository name
			repo_match = re.search(r"Repository: (.+)", summary_str)
			if repo_match:
				summary_dict["repository"] = repo_match.group(1).strip()
			else:
				summary_dict["repository"] = ""

			# Extract files analyzed
			files_match = re.search(r"Files analyzed: (\d+)", summary_str)
			if files_match:
				summary_dict["num_files"] = int(files_match.group(1))
			else:
				summary_dict["num_files"] = None

			# Extract estimated tokens
			tokens_match = re.search(r"Estimated tokens: (.+)", summary_str)
			if tokens_match:
				summary_dict["token_count"] = tokens_match.group(1).strip()
			else:
				summary_dict["token_count"] = ""
								
		except Exception:
			# If any regex operation fails, set default values
			summary_dict["repository"] = ""
			summary_dict["num_files"] = None
			summary_dict["token_count"] = ""

		# Store the original string as well
		summary_dict["raw"] = summary_str
		return summary_dict

	def get_summary(self) -> str:
		"""Returns the repository summary."""
		return self.summary["raw"] if self.summary else ""

	def get_tree(self) -> Any:
		"""Returns the repository tree structure."""
		return self.tree

	async def get_content(self, file_paths: Optional[List[str]] = None) -> str:
		"""Returns the repository content."""
		if file_paths is None:
			return self.content or "No content available."

		if getattr(self, '_is_fallback', False):
			return await self._fetch_raw_files(file_paths)

		return self._get_files_content(file_paths)

	async def _fetch_raw_files(self, file_paths: List[str]) -> str:
		"""Fallback method to fetch files directly from GitHub using raw URLs."""
		base_url = self.url
		if base_url.endswith("/"):
			base_url = base_url[:-1]

		# Parse the GitHub URL to get owner, repo, and branch
		# Format: https://github.com/owner/repo or https://github.com/owner/repo/tree/branch
		match = re.search(r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?", base_url)
		if not match:
			return f"Error: Cannot parse GitHub URL for fallback: {self.url}"

		owner, repo, url_branch = match.groups()

		# Prefer branch from URL regex, then self.branch, then default to "main"
		branch = url_branch or getattr(self, "branch", None) or "main"

		raw_base_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"

		concatenated = ""
		async with httpx.AsyncClient() as client:
			for path in file_paths:
				# Clean up path to avoid double slashes
				clean_path = path.lstrip("/")
				url = f"{raw_base_url}{clean_path}"
				try:
					response = await client.get(url, follow_redirects=True)
					response.raise_for_status()
					content = response.text

					if concatenated:
						concatenated += "\n\n"
					concatenated += f"==================================================\nFile: {path}\n==================================================\n{content}"
				except Exception as e:
					logger.error(f"Failed to fetch {path} via raw URL: {e}")
					# Don't fail completely, just skip or note the error for this file

		if not concatenated:
			return "Could not retrieve content for the specified files."
		return concatenated

	def _get_files_content(self, file_paths: List[str]) -> str:
		"""Helper function to extract specific files from repository content."""
		result = {}
		for path in file_paths:
			result[path] = None
		if not self.content:
			return result
		# Get the content as a string
		content_str = str(self.content)

		# Try multiple patterns to match file content sections
		patterns = [
			# Standard pattern with exactly 50 equals signs
			r"={50}\nFile: ([^\n]+)\n={50}",
			# More flexible pattern with varying number of equals signs
			r"={10,}\nFile: ([^\n]+)\n={10,}",
			# Extra flexible pattern
			r"=+\s*File:\s*([^\n]+)\s*\n=+",
		]

		for pattern in patterns:
			# Find all matches in the content
			matches = re.finditer(pattern, content_str)
			matched = False
			for match in matches:
				matched = True
				# Get the position of the match
				start_pos = match.end()
				filename = match.group(1).strip()
				# Find the next file header or end of string
				next_match = re.search(pattern, content_str[start_pos:])
				if next_match:
					end_pos = start_pos + next_match.start()
					file_content = content_str[start_pos:end_pos].strip()
				else:
					file_content = content_str[start_pos:].strip()

				# Check if this file matches any of the requested paths
				for path in file_paths:
					basename = path.split("/")[-1]
					if path == filename or basename == filename or path.endswith("/" + filename):
						result[path] = file_content
			
			# If we found matches with this pattern, no need to try others
			if matched:
				break

		# Concatenate all found file contents with file headers
		concatenated = ""
		for path, content in result.items():
			if content is not None:
				if concatenated:
					concatenated += "\n\n"
				concatenated += f"==================================================\nFile: {path}\n==================================================\n{content}"
		return concatenated