import pytest
from gitingest_mcp.ingest import GitIngester

# Basic test against a small, real repository to test the happy path without mocks
@pytest.mark.asyncio
async def test_real_repo_fetch():
    # We use a very small repo to keep tests fast and avoid rate limiting
    url = "https://github.com/puravparab/gitingest-mcp"
    ingester = GitIngester(url)

    await ingester.fetch_repo_data()

    # Check that we didn't fall back
    assert not getattr(ingester, '_is_fallback', False)

    summary = ingester.get_summary()
    assert "Repository:" in summary
    assert "Files analyzed:" in summary

    tree = ingester.get_tree()
    assert tree is not None
    assert isinstance(tree, str)
    assert "README.md" in tree

    # Check file content
    content = await ingester.get_content(["README.md"])
    assert "gitingest-mcp" in content.lower()
    assert "README.md" in content

@pytest.mark.asyncio
async def test_real_repo_fetch_branch():
    url = "https://github.com/puravparab/gitingest-mcp"
    ingester = GitIngester(url, branch="main")

    await ingester.fetch_repo_data()
    assert not getattr(ingester, '_is_fallback', False)

    content = await ingester.get_content(["README.md"])
    assert "gitingest-mcp" in content.lower()

@pytest.mark.asyncio
async def test_fallback_mechanism(mocker, respx_mock):
    # Mock ingest to simulate rate-limiting or generic failure
    mocker.patch('gitingest_mcp.ingest.ingest', side_effect=Exception("Rate limit exceeded"))

    url = "https://github.com/puravparab/gitingest-mcp"
    ingester = GitIngester(url, branch="main")

    # This should fail gracefully and enable fallback mode
    await ingester.fetch_repo_data()
    assert getattr(ingester, '_is_fallback', False) is True

    # Summary should indicate fallback
    summary = ingester.get_summary()
    assert "Fallback mode active" in summary

    # Tree should indicate unavailable
    tree = ingester.get_tree()
    assert "unavailable in fallback mode" in tree

    import httpx

    # Test fallback content fetching via raw URL
    # Intercept httpx requests to raw.githubusercontent.com
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

    # missing.txt should not be present in output, since it 404s
    assert "File: missing.txt" not in content

@pytest.mark.asyncio
async def test_parse_summary():
    ingester = GitIngester("https://github.com/test/repo")

    summary_str = "Repository: test/repo\nFiles analyzed: 42\nEstimated tokens: 1234\n"
    summary_dict = ingester._parse_summary(summary_str)

    assert summary_dict["repository"] == "test/repo"
    assert summary_dict["num_files"] == 42
    assert summary_dict["token_count"] == "1234"
    assert summary_dict["raw"] == summary_str

@pytest.mark.asyncio
async def test_parse_summary_invalid():
    ingester = GitIngester("https://github.com/test/repo")

    summary_str = "Invalid summary format without expected fields"
    summary_dict = ingester._parse_summary(summary_str)

    assert summary_dict["repository"] == ""
    assert summary_dict["num_files"] is None
    assert summary_dict["token_count"] == ""
    assert summary_dict["raw"] == summary_str

@pytest.mark.asyncio
async def test_get_files_content():
    ingester = GitIngester("https://github.com/test/repo")
    ingester.content = "==================================================\nFile: test.py\n==================================================\nprint('hello world')\n\n==================================================\nFile: README.md\n==================================================\n# Hello"

    # Test specific file retrieval via regex patterns
    content = await ingester.get_content(["test.py"])
    assert "test.py" in content
    assert "hello world" in content
    assert "README.md" not in content

    # Test getting all content when no file paths are specified
    content_all = await ingester.get_content()
    assert "test.py" in content_all
    assert "README.md" in content_all
