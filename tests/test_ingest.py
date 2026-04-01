import sys
from unittest.mock import MagicMock

# Mock dependencies to allow importing GitIngester without network access
mock_gitingest = MagicMock()
sys.modules['gitingest'] = mock_gitingest
sys.modules['mcp'] = MagicMock()
sys.modules['mcp.server'] = MagicMock()
sys.modules['mcp.server.fastmcp'] = MagicMock()

from gitingest_mcp.ingest import GitIngester
import pytest

def test_get_files_content_with_empty_content():
    ingester = GitIngester("https://github.com/user/repo")
    # self.content is None by default
    assert ingester.content is None

    # This should return a string, but currently it returns a dict {}
    result = ingester._get_files_content(["test.py"])

    assert isinstance(result, str), f"Expected string, got {type(result)}"
    assert result == ""

def test_get_files_content_with_actual_content():
    ingester = GitIngester("https://github.com/user/repo")
    ingester.content = """==================================================
File: test.py
==================================================
print('hello')
"""
    result = ingester._get_files_content(["test.py"])
    assert isinstance(result, str)
    assert "File: test.py" in result
    assert "print('hello')" in result
