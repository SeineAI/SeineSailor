import os
import json
from github import Github
from options import Options
from prompts import Prompts
from commenter import Commenter, COMMENT_REPLY_TAG, COMMENT_TAG, SUMMARIZE_TAG
from inputs import Inputs
from octokit import octokit
from tokenizer import get_token_count
from bot import Bot
from logger import setup_logger

logger = setup_logger("review_comment")

context = Github().context
repo = context.repo
ASK_BOT = "@SeineSailor"


async def handle_review_comment(heavy_bot: Bot, options: Options, prompts: Prompts):
    commenter = Commenter()
    inputs = Inputs()

    if context.event_name != "pull_request_review_comment":
        logger.warning(f"Skipped: {context.event_name} is not a pull_request_review_comment event")
        return

    if not context.payload:
        logger.warning(f"Skipped: {context.event_name} event is missing payload")
        return

    comment = context.payload.comment
    if comment is None:
        logger.warning(f"Skipped: {context.event_name} event is missing comment")
        return

    if context.payload.pull_request is None or context.payload.repository is None:
        logger.warning(f"Skipped: {context.event_name} event is missing pull_request")
        return

    inputs.title = context.payload.pull_request.title
    if context.payload.pull_request.body:
        inputs.description = commenter.get_description(context.payload.pull_request.body)

    if context.payload.action != "created":
        logger.warning(f"Skipped: {context.event_name} event is not created")
        return

    if not (comment.body.includes(COMMENT_TAG) or comment.body.includes(COMMENT_REPLY_TAG)):
        pull_number = context.payload.pull_request.number

        inputs.comment = f"{comment.user.login}: {comment.body}"
        inputs.diff = comment.diff_hunk
        inputs.filename = comment.path

        comment_chain, top_level_comment = await commenter.get_comment_chain(pull_number, comment)

        if not top_level_comment:
            logger.warning("Failed to find the top-level comment to reply to")
            return

        inputs.comment_chain = comment_chain

        if COMMENT_TAG in comment_chain or COMMENT_REPLY_TAG in comment_chain or ASK_BOT in comment.body:
            file_diff = ""
            try:
                diff_all = await octokit.repos.compare_commits(
                    owner=repo.owner.login,
                    repo=repo.name,
                    base=context.payload.pull_request.base.sha,
                    head=context.payload.pull_request.head.sha
                )
                if diff_all.data:
                    files = diff_all.data.files
                    if files:
                        file = next((f for f in files if f.filename == comment.path), None)
                        if file and file.patch:
                            file_diff = file.patch
            except Exception as e:
                logger.warning(f"Failed to get file diff: {e}, skipping.")

            if not inputs.diff:
                if file_diff:
                    inputs.diff = file_diff
                    file_diff = ""
                else:
                    await commenter.review_comment_reply(
                        pull_number,
                        top_level_comment,
                        "Cannot reply to this comment as diff could not be found."
                    )
                    return

            tokens = get_token_count(prompts.render_comment(inputs))

            if tokens > options.heavy_token_limits.request_tokens:
                await commenter.review_comment_reply(
                    pull_number,
                    top_level_comment,
                    "Cannot reply to this comment as diff being commented is too large and exceeds the token limit."
                )
                return

            if file_diff:
                file_diff_count = prompts.comment.count("$file_diff")
                file_diff_tokens = get_token_count(file_diff)
                if file_diff_count > 0 and tokens + file_diff_tokens * file_diff_count <= options.heavy_token_limits.request_tokens:
                    tokens += file_diff_tokens * file_diff_count
                    inputs.file_diff = file_diff

            summary = await commenter.find_comment_with_tag(SUMMARIZE_TAG, pull_number)
            if summary:
                short_summary = commenter.get_short_summary(summary.body)
                short_summary_tokens = get_token_count(short_summary)
                if tokens + short_summary_tokens <= options.heavy_token_limits.request_tokens:
                    tokens += short_summary_tokens
                    inputs.short_summary = short_summary

            reply, _ = await heavy_bot.chat(prompts.render_comment(inputs), {})

            await commenter.review_comment_reply(pull_number, top_level_comment, reply)
        else:
            logger.info(f"Skipped: {context.event_name} event is from the bot itself")

