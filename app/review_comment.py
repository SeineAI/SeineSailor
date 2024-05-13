from app.options import Options
from app.prompts import Prompts
from app.commenter import COMMENT_REPLY_TAG, COMMENT_TAG, SUMMARIZE_TAG
from app.inputs import Inputs
from app.tokenizer import get_token_count
from app.bot import Bot
from app.context import commenter, context, repo
from app.logger import setup_logger

# Setup logger
logger = setup_logger("review_comment")

ASK_BOT = "@SeineSailor"


async def handle_review_comment(heavy_bot: Bot, options: Options, prompts: Prompts):
    if context["event_name"] != "pull_request_review_comment":
        logger.warning(f"Skipped: {context['event_name']} is not a pull_request_review_comment event")
        return

    comment = context["payload"].get("comment")
    if not comment:
        logger.warning(f"Skipped: {context['event_name']} event is missing comment")
        return

    pr_data = context["payload"].get("pull_request")
    if not pr_data or not context["payload"].get("repository"):
        logger.warning(f"Skipped: {context['event_name']} event is missing pull_request or repository")
        return

    inputs = Inputs()
    inputs.title = pr_data.get("title", "")
    pr_body = pr_data.get("body")
    if pr_body:
        inputs.description = commenter.get_description(pr_body)

    if context["payload"].get("action") != "created":
        logger.warning(f"Skipped: {context['event_name']} event is not created")
        return

    if COMMENT_TAG not in comment["body"] and COMMENT_REPLY_TAG not in comment["body"]:
        pull_number = pr_data["number"]
        inputs.comment = f"{comment['user']['login']}: {comment['body']}"
        inputs.diff = comment.get("diff_hunk", "")
        inputs.filename = comment["path"]

        comment_obj = commenter.get_pull_request_comment(pull_number, comment['id'])
        comment_chain_result = await commenter.get_comment_chain(pull_number, comment_obj)
        comment_chain = comment_chain_result["chain"]
        top_level_comment = comment_chain_result["top_level_comment"]

        if not top_level_comment:
            logger.warning("Failed to find the top-level comment to reply to")
            return

        inputs.comment_chain = comment_chain

        if COMMENT_TAG in comment_chain or COMMENT_REPLY_TAG in comment_chain or ASK_BOT in comment["body"]:
            file_diff = ""
            try:
                # get diff for this file by comparing the base and head commits
                diff_all = repo.compare(pr_data["base"]["sha"], pr_data["head"]["sha"])
                files = diff_all.files if diff_all else None

                if files:
                    file_info = next((f for f in files if f.filename == comment["path"]), None)
                    if file_info and file_info.patch:
                        file_diff = file_info.patch

            except Exception as error:
                logger.warning(f"Failed to get file diff: {error}, skipping.")

            if not inputs.diff and file_diff:
                inputs.diff = file_diff
                file_diff = ""

            elif not inputs.diff:
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

                if (file_diff_count and tokens + file_diff_tokens * file_diff_count
                        <= options.heavy_token_limits.request_tokens):
                    tokens += file_diff_tokens * file_diff_count
                    inputs.file_diff = file_diff

            summary = await commenter.find_comment_with_tag(SUMMARIZE_TAG, pull_number)
            if summary:
                short_summary = commenter.get_short_summary(summary.body)
                short_summary_tokens = get_token_count(short_summary)

                if tokens + short_summary_tokens <= options.heavy_token_limits.request_tokens:
                    tokens += short_summary_tokens
                    inputs.short_summary = short_summary

            reply = await heavy_bot.chat(prompts.render_comment(inputs))

            await commenter.review_comment_reply(pull_number, top_level_comment, reply)

    else:
        logger.info(f"Skipped: {context['event_name']} event is from the bot itself")
