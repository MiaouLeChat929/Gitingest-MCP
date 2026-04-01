import re
import asyncio
from gitingest import ingest
from typing import Any, Dict, List, Optional

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
		loop = asyncio.get_event_loop()
		summary, self.tree, self.content = await loop.run_in_executor(
			None, lambda: ingest(self.url)
		)
		self.summary = self._parse_summary(summary)

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
		return self.summary["raw"]

	def get_tree(self) -> Any:
		"""Returns the repository tree structure."""
		return self.tree

	def get_content(self, file_paths: Optional[List[str]] = None) -> str:
		"""Returns the repository content."""
		if file_paths is None:
			return self.content
		return self._get_files_content(file_paths)

	def _get_files_content(self, file_paths: List[str]) -> str:
		"""Helper function to extract specific files from repository content."""
		result = {}
		for path in file_paths:
			result[path] = None
		if not self.content:
			return ""
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