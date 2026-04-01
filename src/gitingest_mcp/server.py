from fastmcp import FastMCP
from gitingest_mcp.ingest import GitIngester
from typing import Any, Dict, Union, List, Optional
import logging

logger = logging.getLogger('gitingest-mcp')

# Initialize FastMCP server using FastMCP 3.0 API
mcp = FastMCP("gitingest-mcp", instructions="Provides tools to explore and ingest GitHub repository structures and file contents. Start by getting the repository summary to understand its scope, then explore the tree or read specific files.")

@mcp.tool()
async def git_summary(
    owner: str,
    repo: str,
    branch: Optional[str] = None
) -> str:
    """
    Get a high-level summary of a GitHub repository, including its estimated size and README.
    Use this tool first to understand what the repository is about and gauge its overall size before diving into specific files.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()
        summary = ingester.get_summary()

        try:
            # Try to fetch README.md for context
            readme_content = await ingester.get_content(["README.md"])
            if readme_content and "README.md" in readme_content:
                summary = f"{summary}\n\n{readme_content}"
        except Exception:
            pass

        return summary + "\n\nTip: You can now explore the directory structure to find relevant files, or read specific files if you already know their paths."

    except Exception as e:
        logger.error(f"Failed to get repository summary: {e}")
        return f"Error: Failed to get repository summary. {str(e)}"

@mcp.tool()
async def git_tree(
    owner: str,
    repo: str,
    branch: Optional[str] = None
) -> str:
    """
    Get the complete directory and file structure of a GitHub repository.
    Use this tool to discover file paths that you might want to read next.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        tree_output = ingester.get_tree()
        if not tree_output:
            return "Error: Could not retrieve the repository tree structure."

        return f"Repository Tree:\n{tree_output}\n\nTip: Identify the files that are most relevant to your task and read their contents to proceed."
    except Exception as e:
        logger.error(f"Failed to get repository tree: {e}")
        return f"Error: Failed to get repository tree. {str(e)}"

@mcp.tool()
async def git_files(
    owner: str,
    repo: str,
    file_paths: List[str],
    branch: Optional[str] = None
) -> str:
    """
    Read the contents of specific files from a GitHub repository.
    Provide the exact paths (as seen in the repository tree) of the files you need to examine.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        files_content = await ingester.get_content(file_paths)
        if not files_content or "Could not retrieve" in files_content:
            return f"Error: None of the requested files were found. Please verify the paths from the repository tree."

        return f"{files_content}\n\nTip: If you need more context, consider reading related files or checking the imports/exports."

    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        return f"Error: Failed to get file content. {str(e)}"

def main():
    """Entry point for the gitingest-mcp command."""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()