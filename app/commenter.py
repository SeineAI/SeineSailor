import os
import re
from typing import List, Dict, Optional
from github import Repository, IssueComment, PullRequestComment
from logger import setup_logger

logger = setup_logger("commenter")

# Define constants
COMMENT_GREETING = f"{os.getenv('BOT_ICON', '🤖')}   SeineSailor"
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
    def __init__(self, repo: Repository):
        self.repo = repo
        self.review_comments_cache: Dict[int, List[PullRequestComment]] = {}
        self.issue_comments_cache: Dict[int, List[IssueComment]] = {}
        self.review_comments_buffer: List[Dict] = []

    async def comment(self, message: str, tag: str, mode: str, target: int):
        if not tag:
            tag = COMMENT_TAG

        body = f"{COMMENT_GREETING}\n\n{message}\n\n{tag}"

        if mode == "create":
            await self.create(body, target)
        else:
            await self.replace(body, tag, target)

    async def create(self, body: str, target: int):
        try:
            comment = self.repo.get_issue(number=target).create_comment(body)
            if target in self.issue_comments_cache:
                self.issue_comments_cache[target].append(comment)
            else:
                self.issue_comments_cache[target] = [comment]
        except Exception as e:
            logger.warning(f"Failed to create comment: {e}")

    async def replace(self, body: str, tag: str, target: int):
        try:
            cmt = await self.find_comment_with_tag(tag, target)
            if cmt:
                cmt.edit(body=body)
            else:
                await self.create(body, target)
        except Exception as e:
            logger.warning(f"Failed to replace comment: {e}")

    async def find_comment_with_tag(self, tag: str, target: int) -> Optional[IssueComment]:
        comments = await self.list_comments(target)
        for cmt in comments:
            if tag in cmt.body:
                return cmt
        return None

    def get_content_within_tags(self, content: str, start_tag: str, end_tag: str) -> str:
        start = content.find(start_tag)
        end = content.find(end_tag)
        if start >= 0 and end >= 0:
            return content[start + len(start_tag):end]
        return ""

    def remove_content_within_tags(self, content: str, start_tag: str, end_tag: str) -> str:
        start = content.find(start_tag)
        end = content.find(end_tag)
        if start >= 0 and end >= 0:
            return content[:start] + content[end + len(end_tag):]
        return content

    def get_raw_summary(self, summary: str) -> str:
        return self.get_content_within_tags(summary, RAW_SUMMARY_START_TAG, RAW_SUMMARY_END_TAG)

    def get_short_summary(self, summary: str) -> str:
        return self.get_content_within_tags(summary, SHORT_SUMMARY_START_TAG, SHORT_SUMMARY_END_TAG)

    def get_description(self, description: str) -> str:
        return self.remove_content_within_tags(description, DESCRIPTION_START_TAG, DESCRIPTION_END_TAG)

    def get_release_notes(self, description: str) -> str:
        release_notes = self.get_content_within_tags(description, DESCRIPTION_START_TAG, DESCRIPTION_END_TAG)
        return re.sub(r"(^|\n)> .*", "", release_notes)

    async def update_description(self, pull_number: int, message: str):
        try:
            pr = self.repo.get_pull(pull_number)
            body = pr.body or ""
            description = self.get_description(body)

            message_clean = self.remove_content_within_tags(message, DESCRIPTION_START_TAG, DESCRIPTION_END_TAG)
            new_description = f"{description}\n{DESCRIPTION_START_TAG}\n{message_clean}\n{DESCRIPTION_END_TAG}"
            pr.edit(body=new_description)
        except Exception as e:
            logger.warning(f"Failed to get PR: {e}, skipping adding release notes to description.")

    async def buffer_review_comment(self, path: str, start_line: int, end_line: int, message: str):
        message = f"{COMMENT_GREETING}\n\n{message}\n\n{COMMENT_TAG}"
        self.review_comments_buffer.append({
            "path": path,
            "start_line": start_line,
            "end_line": end_line,
            "message": message
        })

    async def delete_pending_review(self, pull_number: int):
        try:
            reviews = list(self.repo.get_pull(pull_number).get_reviews())
            pending_review = next((review for review in reviews if review.state == "PENDING"), None)

            if pending_review:
                logger.info(f"Deleting pending review for PR #{pull_number} id: {pending_review.id}")
                try:
                    self.repo.get_pull(pull_number).dismiss_review(pending_review.id, "Removing pending review")
                except Exception as e:
                    logger.warning(f"Failed to delete pending review: {e}")
        except Exception as e:
            logger.warning(f"Failed to list reviews: {e}")

    async def submit_review(self, pull_number: int, status_msg: str):
        body = f"{COMMENT_GREETING}\n\n{status_msg}\n"

        if len(self.review_comments_buffer) == 0:
            logger.info(f"Submitting empty review for PR #{pull_number}")
            try:
                self.repo.get_pull(pull_number).create_review(
                    event="COMMENT",
                    body=body
                )
            except Exception as e:
                logger.warning(f"Failed to submit empty review: {e}")
            return

        try:
            generate_comment_data = lambda comment: {
                "path": comment["path"],
                "body": comment["message"],
                "line": comment["end_line"],
                "start_line": comment["start_line"] if comment["start_line"] != comment["end_line"] else None
            }

            review = self.repo.get_pull(pull_number).create_review(
                event="COMMENT",
                comments=[generate_comment_data(comment) for comment in self.review_comments_buffer]
            )

            logger.info(
                f"Submitting review for PR #{pull_number}, total comments: {len(self.review_comments_buffer)}, review id: {review.id}")

        except Exception as e:
            logger.warning(f"Failed to create review: {e}. Falling back to individual comments.")
            await self.delete_pending_review(pull_number)

            for i, comment in enumerate(self.review_comments_buffer, start=1):
                try:
                    self.repo.get_pull(pull_number).create_review_comment(
                        path=comment["path"],
                        body=comment["message"],
                        line=comment["end_line"],
                        start_line=comment["start_line"] if comment["start_line"] != comment["end_line"] else None
                    )
                    logger.info(f"Comment {i}/{len(self.review_comments_buffer)} posted")
                except Exception as ee:
                    logger.warning(f"Failed to create review comment: {ee}")

    async def review_comment_reply(self, pull_number: int, top_level_comment: PullRequestComment, message: str):
        reply = f"{COMMENT_GREETING}\n\n{message}\n\n{COMMENT_REPLY_TAG}"

        try:
            self.repo.get_pull(pull_number).create_reply_for_review_comment(
                body=reply,
                comment_id=top_level_comment.id
            )
        except Exception as e:
            logger.warning(f"Failed to reply to the top-level comment {e}")
            try:
                self.repo.get_pull(pull_number).create_reply_for_review_comment(
                    body=f"Could not post the reply due to the following error: {e}",
                    comment_id=top_level_comment.id
                )
            except Exception as ee:
                logger.warning(f"Failed to reply to the top-level comment {ee}")

        try:
            if COMMENT_TAG in top_level_comment.body:
                new_body = top_level_comment.body.replace(COMMENT_TAG, COMMENT_REPLY_TAG)
                top_level_comment.edit(body=new_body)
        except Exception as error:
            logger.warning(f"Failed to update the top-level comment {error}")

    async def get_comments_within_range(self, pull_number: int, path: str, start_line: int, end_line: int):
        comments = await self.list_review_comments(pull_number)
        return [
            comment for comment in comments
            if comment.path == path and
               comment.body and
               ((comment.start_line is not None and comment.start_line >= start_line and comment.line <= end_line) or
                (start_line == end_line and comment.line == end_line))
        ]

    async def get_comments_at_range(self, pull_number: int, path: str, start_line: int, end_line: int):
        comments = await self.list_review_comments(pull_number)
        return [
            comment for comment in comments
            if comment.path == path and
               comment.body and
               ((comment.start_line is not None and comment.start_line == start_line and comment.line == end_line) or
                (start_line == end_line and comment.line == end_line))
        ]

    async def get_comment_chains_within_range(self, pull_number: int, path: str, start_line: int, end_line: int,
                                              tag=""):
        existing_comments = await self.get_comments_within_range(pull_number, path, start_line, end_line)
        top_level_comments = [comment for comment in existing_comments if not comment.in_reply_to_id]

        all_chains = ""
        for chain_num, top_level_comment in enumerate(top_level_comments, start=1):
            chain = await self.compose_comment_chain(existing_comments, top_level_comment)
            if chain and tag in chain:
                all_chains += f"Conversation Chain {chain_num}:\n{chain}\n---\n"

        return all_chains

    async def compose_comment_chain(self, review_comments: List[PullRequestComment],
                                    top_level_comment: PullRequestComment) -> str:
        conversation_chain = [
                                 f"{top_level_comment.user.login}: {top_level_comment.body}"
                             ] + [
                                 f"{cmt.user.login}: {cmt.body}"
                                 for cmt in review_comments
                                 if cmt.in_reply_to_id == top_level_comment.id
                             ]

        return "\n---\n".join(conversation_chain)

    async def get_comment_chain(self, pull_number: int, comment: PullRequestComment):
        try:
            review_comments = await self.list_review_comments(pull_number)
            top_level_comment = await self.get_top_level_comment(review_comments, comment)
            chain = await self.compose_comment_chain(review_comments, top_level_comment)
            return {"chain": chain, "top_level_comment": top_level_comment}
        except Exception as e:
            logger.warning(f"Failed to get conversation chain: {e}")
            return {"chain": "", "top_level_comment": None}

    async def get_top_level_comment(self, review_comments: List[PullRequestComment],
                                    comment: PullRequestComment) -> PullRequestComment:
        top_level_comment = comment

        while top_level_comment.in_reply_to_id:
            parent_comment = next((cmt for cmt in review_comments if cmt.id == top_level_comment.in_reply_to_id), None)

            if parent_comment:
                top_level_comment = parent_comment
            else:
                break

        return top_level_comment

    async def list_review_comments(self, target: int) -> List[PullRequestComment]:
        if target in self.review_comments_cache:
            return self.review_comments_cache[target]

        all_comments = []
        page = 1
        while True:
            try:
                comments = list(self.repo.get_pull(target).get_review_comments(page=page, per_page=100))
                all_comments.extend(comments)
                page += 1
                if not comments or len(comments) < 100:
                    break
            except Exception as e:
                logger.warning(f"Failed to list review comments: {e}")
                break

        self.review_comments_cache[target] = all_comments
        return all_comments

    async def list_comments(self, target: int) -> List[IssueComment]:
        if target in self.issue_comments_cache:
            return self.issue_comments_cache[target]

        all_comments = []
        page = 1
        while True:
            try:
                comments = list(self.repo.get_issue(number=target).get_comments(page=page, per_page=100))
                all_comments.extend(comments)
                page += 1
                if not comments or len(comments) < 100:
                    break
            except Exception as e:
                logger.warning(f"Failed to list comments: {e}")
                break

        self.issue_comments_cache[target] = all_comments
        return all_comments

    def get_reviewed_commit_ids(self, comment_body: str) -> List[str]:
        start = comment_body.find(COMMIT_ID_START_TAG)
        end = comment_body.find(COMMIT_ID_END_TAG)
        if start == -1 or end == -1:
            return []

        ids = comment_body[start + len(COMMIT_ID_START_TAG):end]
        return [id.replace("-->", "").strip() for id in ids.split("<!--") if id.replace("-->", "").strip()]

    def get_reviewed_commit_ids_block(self, comment_body: str) -> str:
        start = comment_body.find(COMMIT_ID_START_TAG)
        end = comment_body.find(COMMIT_ID_END_TAG)
        if start == -1 or end == -1:
            return ""

        return comment_body[start:end + len(COMMIT_ID_END_TAG)]

    def add_reviewed_commit_id(self, comment_body: str, commit_id: str) -> str:
        start = comment_body.find(COMMIT_ID_START_TAG)
        end = comment_body.find(COMMIT_ID_END_TAG)
        if start == -1 or end == -1:
            return f"{comment_body}\n{COMMIT_ID_START_TAG}\n<!-- {commit_id} -->\n{COMMIT_ID_END_TAG}"

        ids = comment_body[start + len(COMMIT_ID_START_TAG):end]
        return f"{comment_body[:start + len(COMMIT_ID_START_TAG)]}{ids}<!-- {commit_id} -->\n{comment_body[end:]}"

    def get_highest_reviewed_commit_id(self, commit_ids: List[str], reviewed_commit_ids: List[str]) -> str:
        for commit_id in reversed(commit_ids):
            if commit_id in reviewed_commit_ids:
                return commit_id
        return ""

    async def get_all_commit_ids(self, pull_number: int) -> List[str]:
        all_commits = []
        page = 1
        while True:
            try:
                commits = list(self.repo.get_pull(pull_number).get_commits(page=page, per_page=100))
                all_commits.extend([commit.sha for commit in commits])
                page += 1
                if not commits or len(commits) < 100:
                    break
            except Exception as e:
                logger.warning(f"Failed to list commits: {e}")
                break

        return all_commits

    def add_in_progress_status(self, comment_body: str, status_msg: str) -> str:
        start = comment_body.find(IN_PROGRESS_START_TAG)
        end = comment_body.find(IN_PROGRESS_END_TAG)

        if start == -1 or end == -1:
            return f"""{IN_PROGRESS_START_TAG}

Currently reviewing new changes in this PR...

{status_msg}

{IN_PROGRESS_END_TAG}

---

{comment_body}"""
        return comment_body

    def remove_in_progress_status(self, comment_body: str) -> str:
        start = comment_body.find(IN_PROGRESS_START_TAG)
        end = comment_body.find(IN_PROGRESS_END_TAG)

        if start != -1 and end != -1:
            return comment_body[:start] + comment_body[end + len(IN_PROGRESS_END_TAG):]
        return comment_body
