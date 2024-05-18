from app.options import Options
from app.prompts import Prompts
from app.bot import Bot
from app.context import commenter, context, repo
from app.logger import setup_logger

# Setup logger
logger = setup_logger("review_comment")

ASK_BOT = "@SeineSailor"


async def handle_issue_comment(heavy_bot: Bot, options: Options, prompts: Prompts):
    if context["event_name"] != "issue_comment":
        logger.warning(f"Skipped: {context['event_name']} is not a issue_comment event")
        return

    comment = context["payload"].get("comment")
    if not comment:
        logger.warning(f"Skipped: {context['event_name']} event is missing comment")
        return

    issue = context["payload"].get("issue")
    if not issue:
        logger.warning(f"Skipped: {context['event_name']} event is missing issue")
        return

    pr_data = issue.get("pull_request")
    if not pr_data or not context["payload"].get("repository"):
        logger.warning(f"Skipped: {context['event_name']} event is missing pull_request or repository")
        return