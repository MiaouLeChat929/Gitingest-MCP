from fastmcp import FastMCP
from gitingest_mcp.ingest import GitIngester
from typing import Any, Dict, Union, List, Optional, Annotated
from pydantic import Field
import logging

logger = logging.getLogger('gitingest-mcp')

mcp = FastMCP(
    "gitingest-mcp",
    instructions="Provides capabilities to explore and ingest GitHub repository structures and file contents. A recommended pattern is to first acquire the repository summary to gauge its scope, then navigate the directory tree to identify pertinent files, and finally retrieve specific file contents."
)

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_summary(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    branch: Annotated[Optional[str], Field(description="The branch name to analyze. If omitted, attempts to default to 'main' or 'master'")] = None
) -> str:
    """
    Acquires a high-level overview of a GitHub repository, returning its estimated token size, file count, and the README content if available.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()
        summary = ingester.get_summary()

        try:
            readme_content = await ingester.get_content(["README.md"])
            if readme_content and "README.md" in readme_content:
                summary = f"{summary}\n\n{readme_content}"
        except Exception:
            pass

        return summary + "\n\nTip: The directory structure can be examined next to locate domain-specific logic or related configurations."

    except Exception as e:
        logger.error(f"Failed to get repository summary: {e}")
        return f"Error: The repository summary could not be retrieved. {str(e)}"

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_tree(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    branch: Annotated[Optional[str], Field(description="The branch name to analyze. If omitted, attempts to default to 'main' or 'master'")] = None
) -> str:
    """
    Retrieves the comprehensive directory and file structure of a GitHub repository.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        tree_output = ingester.get_tree()
        if not tree_output:
            return "Error: The repository tree structure could not be retrieved."

        return f"Repository Tree:\n{tree_output}\n\nTip: The contents of identified files of interest can be requested to proceed with the analysis."
    except Exception as e:
        logger.error(f"Failed to get repository tree: {e}")
        return f"Error: The repository tree could not be retrieved. {str(e)}"

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_files(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    file_paths: Annotated[List[str], Field(description="A list of exact file paths (as seen in the repository tree) to retrieve")],
    branch: Annotated[Optional[str], Field(description="The branch name to analyze. If omitted, attempts to default to 'main' or 'master'")] = None
) -> str:
    """
    Retrieves the text contents of specified files from a GitHub repository.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        files_content = await ingester.get_content(file_paths)
        if not files_content or "Could not retrieve" in files_content:
            return f"Error: None of the requested files were found. Validating the paths against the repository tree is recommended."

        return f"{files_content}\n\nTip: If the current context is insufficient, related imports, exports, or configurations discovered within these files may warrant further examination."

    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        return f"Error: The file contents could not be retrieved. {str(e)}"

def main():
    """Entry point for the gitingest-mcp command."""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()