import os
from github import Github
from logger import setup_logger

logger = setup_logger("octokit")

token = os.environ.get("GITHUB_TOKEN")
octokit = Github(token)
