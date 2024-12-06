import os
import pytest
import requests_mock
from unittest.mock import patch
from claude_review import get_pr_diff, post_review_comment, main

@pytest.fixture
def mock_env():
    os.environ["GITHUB_TOKEN"] = "test_token"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    yield
    del os.environ["GITHUB_TOKEN"]
    del os.environ["GITHUB_REPOSITORY"]

def test_get_pr_diff(mock_env):
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://api.github.com/repos/owner/repo/pulls/123",
            headers={"Accept": "application/vnd.github.v3.diff"},
            text="diff content"
        )
        diff = get_pr_diff()
        assert diff == "diff content"

def test_post_review_comment(mock_env, capsys):
    with requests_mock.Mocker() as mock:
        mock.post(
            "https://api.github.com/repos/owner/repo/issues/123/comments",
            status_code=201,
            json={"id": 1234, "html_url": "https://example.com/comment"}
        )
        post_review_comment("This is a test comment")
        captured = capsys.readouterr()
        assert "Comment posted successfully:" in captured.out

@patch("claude_review.get_pr_diff")
@patch("claude_review.post_review_comment")
def test_main(mock_post_review_comment, mock_get_pr_diff, mock_env):
    mock_get_pr_diff.return_value = "diff content"
    mock_post_review_comment.return_value = None

    main()

    mock_get_pr_diff.assert_called_once()
    mock_post_review_comment.assert_called_once_with(
        "Please review this code diff and provide actionable feedback:\ndiff content"
    )