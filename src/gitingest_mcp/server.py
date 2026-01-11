import httpx
from mcp.server.fastmcp import FastMCP, Context
from gitingest import ingest_async
from typing import Any, Dict, Union, List, Optional

# Initialize FastMCP server
mcp = FastMCP("gitingest-mcp")

def _construct_url(owner: str, repo: str, token: Optional[str] = None) -> str:
    """Constructs the GitHub URL, injecting the token if provided."""
    if token:
        return f"https://{token}@github.com/{owner}/{repo}"
    return f"https://github.com/{owner}/{repo}"

@mcp.tool()
async def git_summary(
    owner: str,
    repo: str,
    branch: Optional[str] = None,
    token: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Generates a high-level digest of a GitHub repository.

    Use this tool FIRST when introduced to a new repository.
    It returns:
    1. Metadata (file count, token estimation).
    2. The full directory tree structure.
    3. The README.md content (if available).

    It does NOT return the code of all files. Use `git_files` for that.

    Args:
        owner: GitHub username or organization (e.g., 'fastmcp').
        repo: Repository name (e.g., 'fastmcp').
        branch: (Optional) Specific branch to analyze.
        token: (Optional) GitHub PAT for private repositories.
    """
    url = _construct_url(owner, repo, token)
    if ctx:
        await ctx.info(f"Fetching summary for {owner}/{repo}...")

    try:
        # max_file_size=0 ensures we don't fetch all file contents, just summary/tree
        summary, tree, _ = await ingest_async(
            url,
            max_file_size=0,
            branch=branch
        )

        # We try to fetch README specifically to append it
        readme_content = ""
        try:
             _, _, content = await ingest_async(
                url,
                include_patterns=["README.md"],
                branch=branch
            )
             if content:
                 readme_content = f"\n\n{content}"
        except Exception:
            pass # Ignore if README fetch fails

        return f"{summary}\n\n{tree}{readme_content}"

    except Exception as e:
        return f'{{"error": "Failed to get repository summary: {str(e)}. Please check the spelling or provide a token for private repos."}}'

@mcp.tool()
async def git_files(
    owner: str,
    repo: str,
    file_paths: List[str],
    branch: Optional[str] = None,
    token: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Fetches the actual text content of specific files from a repository.

    Use this tool AFTER `git_summary` to read the code of interesting files found in the tree.
    You can request multiple files at once. The output is formatted as a single text digest
    optimized for LLM reasoning.

    Args:
        owner: GitHub username or organization.
        repo: Repository name.
        file_paths: List of exact file paths to fetch (e.g., ["src/main.py", "pyproject.toml"]).
        branch: (Optional) Specific branch.
        token: (Optional) GitHub PAT for private repositories.
    """
    url = _construct_url(owner, repo, token)
    if ctx:
        await ctx.info(f"Fetching files {file_paths} from {owner}/{repo}...")

    try:
        # Use include_patterns to surgically fetch files
        _, _, content = await ingest_async(
            url,
            include_patterns=file_paths,
            branch=branch
        )
        if not content:
             return f'{{"error": "None of the requested files were found in the repository."}}'
        return content

    except Exception as e:
        return f'{{"error": "Failed to get file content: {str(e)}. Please check the spelling or provide a token for private repos."}}'

@mcp.tool()
async def git_search(
    owner: str,
    repo: str,
    pattern: str,
    branch: Optional[str] = None,
    token: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Scans the repository for files matching a glob pattern and returns their content.

    Use this to find files when you don't know the exact path, or to fetch all files
    of a specific type (e.g., all Markdown files or all Python files in a folder).

    Args:
        owner: GitHub username or organization.
        repo: Repository name.
        pattern: Glob pattern to match (e.g., "**/*.md", "src/**/*.py").
        branch: (Optional) Specific branch.
        token: (Optional) GitHub PAT for private repositories.
    """
    url = _construct_url(owner, repo, token)
    if ctx:
        await ctx.info(f"Searching for pattern '{pattern}' in {owner}/{repo}...")

    try:
        _, _, content = await ingest_async(
            url,
            include_patterns=[pattern],
            branch=branch
        )
        if not content:
             return f'{{"error": "No files matching the pattern were found."}}'
        return content
    except Exception as e:
        return f'{{"error": "Failed to search repository: {str(e)}. Please check the spelling or provide a token for private repos."}}'

@mcp.resource("git://{owner}/{repo}/tree")
async def resource_tree(owner: str, repo: str) -> str:
    """
    A read-only resource providing the directory structure of a repository.
    Accessing this resource is equivalent to running `git_summary` but is
    semantic and cacheable by the client.
    """
    url = _construct_url(owner, repo)
    try:
        _, tree, _ = await ingest_async(url, max_file_size=0)
        return tree
    except Exception as e:
         return f"Error fetching tree: {str(e)}"

@mcp.resource("git://{owner}/{repo}/blob/{path}")
async def resource_blob(owner: str, repo: str, path: str) -> str:
    """
    A read-only resource providing the content of a specific file.
    """
    url = _construct_url(owner, repo)
    try:
        _, _, content = await ingest_async(url, include_patterns=[path])
        return content
    except Exception as e:
        return f"Error fetching blob: {str(e)}"

@mcp.prompt()
def digest_repository(owner: str, repo: str) -> str:
    """
    A prompt that asks the AI to analyze a repository architecture.
    """
    return f"""I have loaded the summary for {owner}/{repo}.
Please analyze the architecture based on the file tree and metadata provided by the `git_summary` tool.
Identify key components and suggest where to start reading the code."""

def main():
  """Entry point for the gitingest-mcp command."""
  mcp.run(transport='stdio')

if __name__ == "__main__":
	# Initialize and run the server
	main()
