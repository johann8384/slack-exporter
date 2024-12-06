import json
import os

import requests
from anthropic import Anthropic


def get_pr_number():
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        return json.load(f)["pull_request"]["number"]


def get_pr_diff():
    token = os.environ["GITHUB_TOKEN"]
    pr_number = get_pr_number()
    repo = os.environ["GITHUB_REPOSITORY"]

    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"token {token}"
    }

    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers=headers
        )
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error getting PR diff: {e}")
        return None


def post_review_comment(comment):
    token = os.environ["GITHUB_TOKEN"]
    pr_number = get_pr_number()
    repo = os.environ["GITHUB_REPOSITORY"]

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"body": comment}

    try:
        response = requests.post(
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments",
            headers=headers,
            json=data
        )
        response.raise_for_status()
        print(f"Comment posted successfully: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error posting comment: {e}")


def main():
    diff = get_pr_diff()
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": f"Please review this code diff and provide actionable feedback:\n{diff}"
        }]
    )

    post_review_comment(response.content[0].text)


if __name__ == "__main__":
    main()
