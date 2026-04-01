from fastmcp import FastMCP
from gitingest_mcp.ingest import GitIngester
from typing import Any, Dict, Union, List, Annotated
from pydantic import Field
import logging

logger = logging.getLogger('gitingest-mcp')

mcp = FastMCP(
    "gitingest-mcp",
    instructions="Provides capabilities to explore and ingest GitHub repository structures and file contents by starting with high-level summaries before descending into directory trees and targeted file reads."
)

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_summary(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    branch: Annotated[str, Field(description="The specific branch name to analyze. Use 'main' or 'master' if unknown")] = "main"
) -> str:
    """
    Acquires a high-level overview of a GitHub repository, returning its estimated token size, file count, and the README content to establish initial domain understanding.
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

        return summary + "\n\nBreadcrumb: The repository's directory tree can be examined next to locate domain-specific logic, related configurations, or structural patterns."

    except Exception as e:
        logger.error(f"Failed to get repository summary: {e}")
        return f"Error: The repository summary could not be retrieved due to a network or parsing failure. It is recommended to verify the repository owner, name, and branch validity."

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_tree(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    branch: Annotated[str, Field(description="The specific branch name to analyze. Use 'main' or 'master' if unknown")] = "main"
) -> str:
    """
    Retrieves the comprehensive directory and file structure of a GitHub repository to map out its architectural components.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        tree_output = ingester.get_tree()
        if not tree_output:
            return "Error: The repository tree structure could not be retrieved. It is recommended to verify the repository credentials or branch existence."

        return f"Repository Tree:\n{tree_output}\n\nBreadcrumb: Specific files identified within this tree can be requested to extract the underlying implementation details and proceed with the analysis."
    except Exception as e:
        logger.error(f"Failed to get repository tree: {e}")
        return f"Error: The repository tree could not be retrieved due to a network or parsing failure. It is recommended to verify the repository owner, name, and branch validity."

@mcp.tool(
    annotations={"readOnlyHint": True, "openWorldHint": True}
)
async def git_files(
    owner: Annotated[str, Field(description="The GitHub organization or username owning the repository")],
    repo: Annotated[str, Field(description="The name of the repository")],
    file_paths: Annotated[List[str], Field(description="A list of exact file paths to retrieve as identified within the repository tree")],
    branch: Annotated[str, Field(description="The specific branch name to analyze. Use 'main' or 'master' if unknown")] = "main"
) -> str:
    """
    Retrieves the text contents of specified files from a GitHub repository to analyze implementation details.
    """
    url = f"https://github.com/{owner}/{repo}"

    try:
        ingester = GitIngester(url, branch=branch)
        await ingester.fetch_repo_data()

        files_content = await ingester.get_content(file_paths)
        if not files_content or "Could not retrieve" in files_content:
            return f"Error: None of the requested files were found. Validating the requested paths against the repository tree is strongly recommended."

        return f"{files_content}\n\nBreadcrumb: If the current context remains insufficient, scanning for related imports, exports, or configurations discovered within these files may warrant further targeted retrieval."

    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        return f"Error: The file contents could not be retrieved due to a network or parsing failure. It is recommended to verify the repository owner, name, and branch validity."

def main():
    """Entry point for the gitingest-mcp command."""
    mcp.run(transport='stdio')

if __name__ == "__main__":
    main()