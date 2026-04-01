import pytest
import httpx
from gitingest_mcp.ingest import GitIngester

@pytest.mark.asyncio
async def test_real_repo_fetch_api():
    # Using the real repository to test API approach
    url = "https://github.com/puravparab/gitingest-mcp"
    ingester = GitIngester(url)

    await ingester.fetch_repo_data()

    assert getattr(ingester, '_fetched_from_api', False) is True

    summary = ingester.get_summary()
    assert "Repository: puravparab/gitingest-mcp" in summary
    assert "Files analyzed:" in summary

    tree = ingester.get_tree()
    assert tree is not None
    assert isinstance(tree, str)
    assert "README.md" in tree

    # Check file content (will fallback to raw since we fetched via API)
    content = await ingester.get_content(["README.md"])
    assert "gitingest-mcp" in content.lower()
    assert "README.md" in content

@pytest.mark.asyncio
async def test_fallback_mechanism(mocker, respx_mock):
    # Mock API to fail (e.g., rate limit)
    respx_mock.get("https://api.github.com/repos/puravparab/gitingest-mcp/git/trees/main?recursive=1").mock(
        return_value=httpx.Response(403, json={"message": "API rate limit exceeded"})
    )

    # Master branch API fallback
    respx_mock.get("https://api.github.com/repos/puravparab/gitingest-mcp/git/trees/master?recursive=1").mock(
        return_value=httpx.Response(403, json={"message": "API rate limit exceeded"})
    )

    # Mock ZIP download to fail as well
    respx_mock.get("https://github.com/puravparab/gitingest-mcp/archive/refs/heads/main.zip").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    # Master branch ZIP fallback to fail
    respx_mock.get("https://github.com/puravparab/gitingest-mcp/archive/refs/heads/master.zip").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    url = "https://github.com/puravparab/gitingest-mcp"
    ingester = GitIngester(url, branch="main")

    await ingester.fetch_repo_data()

    assert getattr(ingester, '_fetched_from_api', False) is False
    assert getattr(ingester, '_fetched_from_zip', False) is False

    summary = ingester.get_summary()
    assert "Status: Failed to fetch repository" in summary

    tree = ingester.get_tree()
    assert "Directory structure unavailable" in tree

    # Test fallback content fetching via raw URL
    # Even if main branch ZIP failed, the fallback for direct file fetch
    # will still try main branch first unless we change it manually
    respx_mock.get("https://raw.githubusercontent.com/puravparab/gitingest-mcp/main/README.md").mock(
        return_value=httpx.Response(200, text="# Mocked README\nThis is a mocked fallback.")
    )
    respx_mock.get("https://raw.githubusercontent.com/puravparab/gitingest-mcp/main/missing.txt").mock(
        return_value=httpx.Response(404, text="Not Found")
    )

    content = await ingester.get_content(["README.md", "missing.txt"])

    # Assert successful fetch
    assert "File: README.md" in content
    assert "Mocked README" in content
    assert "File: missing.txt" not in content

@pytest.mark.asyncio
async def test_get_files_content_from_zip_cache():
    url = "https://github.com/test/repo"
    ingester = GitIngester(url)

    # Manually simulate zip fetch cache
    ingester._fetched_from_zip = True
    ingester.files_content = {
        "test.py": "print('hello world')",
        "README.md": "# Hello"
    }

    content = await ingester.get_content(["test.py"])
    assert "test.py" in content
    assert "hello world" in content
    assert "README.md" not in content

    content_multiple = await ingester.get_content(["test.py", "README.md"])
    assert "test.py" in content_multiple
    assert "hello world" in content_multiple
    assert "README.md" in content_multiple
    assert "# Hello" in content_multiple