import os
import json
from github import Github
from github.Repository import Repository
from app.commenter import Commenter
from app.logger import setup_logger

logger = setup_logger("context")

def convert_event_type(event_type):
    # Remove 'Event' suffix
    event_type = event_type.replace('Event', '')
    # Convert CamelCase to snake_case
    snake_case = ''.join(['_' + i.lower() if i.isupper() else i for i in event_type]).lstrip('_')
    return snake_case

# Initialize GitHub client and context
token = os.environ.get("GITHUB_TOKEN")
if not token:
    raise ValueError("GITHUB_TOKEN environment variable is missing.")
github_client = Github(token)

repository = os.getenv("GITHUB_REPOSITORY")
if not repository:
    raise ValueError("GITHUB_REPOSITORY environment variable is missing.")
else:
    logger.debug(f"GITHUB_REPOSITORY:{repository}")
repo: Repository = github_client.get_repo(repository)

redirect_event_name = os.getenv("REDIRECT_EVENT_NAME")
if not redirect_event_name:
    # Load GitHub Actions context
    event_name = os.getenv("GITHUB_EVENT_NAME")
    if not event_name:
        raise ValueError("GITHUB_EVENT_NAME environment variable is missing.")
    else:
        logger.debug(f"GITHUB_EVENT_NAME:{event_name}")

    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("GITHUB_EVENT_PATH environment variable is missing.")
    else:
        logger.debug(f"GITHUB_EVENT_PATH:{event_path}")

    with open(event_path, 'r') as file:
        payload = json.load(file)
else:
    payload = json.loads(os.getenv("REDIRECT_EVENT_PAYLOAD"))
    event_name = redirect_event_name
    logger.debug(f"redirected from {os.getenv('GITHUB_EVENT_NAME')} to {event_name}")

# This is one way to construct the context using the information that we needed in the later code.
# Another way to mimic the `import {context as github_context} from '@actions/github'` behavior, would be to
# dump the GitHub context in the yaml file, then load it here.
# - name: Dump GitHub context
#         env:
#           GITHUB_CONTEXT: ${{ toJson(github) }}
# see https://docs.github.com/en/actions/learn-github-actions/contexts#example-printing-context-information-to-the-log
context = {
    "event_name": event_name,
    "payload": payload
}


# Attempt to retrieve pull request or issue data from the event payload
# pr_data = context.get("pull_request")
# issue_data = context.get("issue")
# comment_data = context.get("comment")

ignore_keyword = "@SeineSailor: ignore"
commenter = Commenter(repo)
