import os
from github import Github
from logger import setup_logger

logger = setup_logger("commenter")

context = Github().context
repo = context.repo

COMMENT_GREETING = f"{os.environ.get('INPUT_BOT_ICON', '')}   SeineSailor"
COMMENT_TAG = "<!-- This is an auto-generated comment by OSS SeineSailor -->"
COMMENT_REPLY_TAG = "<!-- This is an auto-generated reply by OSS SeineSailor -->"
SUMMARIZE_TAG = "<!-- This is an auto-generated comment: summarize by OSS SeineSailor -->"
IN_PROGRESS_START_TAG = "<!-- This is an auto-generated comment: summarize review in progress by OSS SeineSailor -->"
IN_PROGRESS_END_TAG = "<!-- end of auto-generated comment: summarize review in progress by OSS SeineSailor -->"
DESCRIPTION_START_TAG = "<!-- This is an auto-generated comment: release notes by OSS SeineSailor -->"
DESCRIPTION_END_TAG = "<!-- end of auto-generated comment: release notes by OSS SeineSailor -->"
RAW_SUMMARY_START_TAG = "<!-- This is an auto-generated comment: raw summary by OSS SeineSailor -->\n<!--\n"
RAW_SUMMARY_END_TAG = "-->\n<!-- end of auto-generated comment: raw summary by OSS SeineSailor -->"
SHORT_SUMMARY_START_TAG = "<!-- This is an auto-generated comment: short summary by OSS SeineSailor -->\n<!--\n"
SHORT_SUMMARY_END_TAG = "-->\n<!-- end of auto-generated comment: short summary by OSS SeineSailor -->"
COMMIT_ID_START_TAG = "<!-- commit_ids_reviewed_start -->"
COMMIT_ID_END_TAG = "<!-- commit_ids_reviewed_end -->"


class Commenter:
    def __init__(self):
        self.review_comments_buffer = []
        self.review_comments_cache = {}
        self.issue_comments_cache = {}

    async def comment(self, message: str, tag: str, mode: str):

    # ... (implement the comment method)

    def get_content_within_tags(self, content: str, start_tag: str, end_tag: str) -> str:

    # ... (implement the get_content_within_tags method)

    def remove_content_within_tags(self, content: str, start_tag: str, end_tag: str) -> str:

    # ... (implement the remove_content_within_tags method)

    def get_raw_summary(self, summary: str) -> str:

    # ... (implement the get_raw_summary method)

    def get_short_summary(self, summary: str) -> str:

    # ... (implement the get_short_summary method)

    def get_description(self, description: str) -> str:

    # ... (implement the get_description method)

    def get_release_notes(self, description: str) -> str:

    # ... (implement the get_release_notes method)

    async def update_description(self, pull_number: int, message: str):

    # ... (implement the update_description method)

    async def buffer_review_comment(self, path: str, start_line: int, end_line: int, message: str):

    # ... (implement the buffer_review_comment method)

    async def delete_pending_review(self, pull_number: int):

    # ... (implement the delete_pending_review method)

    async def submit_review(self, pull_number: int, commit_id: str, status_msg: str):

    # ... (implement the submit_review method)

    async def review_comment_reply(self, pull_number: int, top_level_comment: dict, message: str):

    # ... (implement the review_comment_reply method)

    async def get_comments_within_range(self, pull_number: int, path: str, start_line: int, end_line: int) -> list:

    # ... (implement the get_comments_within_range method)

    async def get_comments_at_range(self, pull_number: int, path: str, start_line: int, end_line: int) -> list:

    # ... (implement the get_comments_at_range method)

    async def get_comment_chains_within_range(self, pull_number: int, path: str, start_line: int, end_line: int,
                                              tag: str = "") -> str:

    # ... (implement the get_comment_chains_within_range method)

    async def compose_comment_chain(self, review_comments: list, top_level_comment: dict) -> str:

    # ... (implement the compose_comment_chain method)

    async def get_comment_chain(self, pull_number: int, comment: dict) -> dict:

    # ... (implement the get_comment_chain method)

    async def get_top_level_comment(self, review_comments: list, comment: dict) -> dict:

    # ... (implement the get_top_level_comment method)

    async def list_review_comments(self, target: int) -> list:

    # ... (implement the list_review_comments method)

    async def create(self, body: str, target: int):

    # ... (implement the create method)

    async def replace(self, body: str, tag: str, target: int):

    # ... (implement the replace method)

    async def find_comment_with_tag(self, tag: str, target: int) -> dict:

    # ... (implement the find_comment_with_tag method)

    async def list_comments(self, target: int) -> list:

    # ... (implement the list_comments method)

    def get_reviewed_commit_ids(self, comment_body: str) -> list:

    # ... (implement the get_reviewed_commit_ids method)

    def get_reviewed_commit_ids_block(self, comment_body: str) -> str:

    # ... (implement the get_reviewed_commit_ids_block method)

    def add_reviewed_commit_id(self, comment_body: str, commit_id: str) -> str:

    # ... (implement the add_reviewed_commit_id method)

    def get_highest_reviewed_commit_id(self, commit_ids: list, reviewed_commit_ids: list) -> str:

    # ... (implement the get_highest_reviewed_commit_id method)

    async def get_all_commit_ids(self) -> list:

    # ... (implement the get_all_commit_ids method)

    def add_in_progress_status(self, comment_body: str, status_msg: str) -> str:

    # ... (implement the add_in_progress_status method)

    def remove_in_progress_status(self, comment_body: str) -> str:
# ... (implement the remove_in_progress_status method)
