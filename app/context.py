import os
import json
from github import Github
from github.Repository import Repository
from commenter import Commenter


# Load GitHub Actions context
def load_github_context():
    event_path = os.getenv("GITHUB_EVENT_PATH")
    repo_name = os.getenv("GITHUB_REPOSITORY")

    if not event_path or not repo_name:
        raise ValueError("GITHUB_EVENT_PATH or GITHUB_REPOSITORY is missing.")

    with open(event_path, 'r') as file:
        event_data = json.load(file)

    owner, repo = repo_name.split('/')
    return event_data, owner, repo


# Initialize GitHub client and context
token = os.environ.get("GITHUB_TOKEN")
if not token:
    raise ValueError("GITHUB_TOKEN environment variable is missing.")

github_client = Github(token)
event_data, owner, repo_name = load_github_context()
repo: Repository = github_client.get_repo(f"{owner}/{repo_name}")

# Extract Pull Request information from the event data
if "pull_request" in event_data:
    pr_data = event_data["pull_request"]
else:
    raise ValueError("No pull_request data found in the event payload.")

ignore_keyword = "@SeineSailor: ignore"
commenter = Commenter(repo)
