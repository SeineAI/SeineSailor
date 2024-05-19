import re
import base64
import asyncio
from typing import List, Tuple, Optional, Dict
from app.options import Options
from app.prompts import Prompts
from app.commenter import COMMENT_REPLY_TAG, RAW_SUMMARY_END_TAG, RAW_SUMMARY_START_TAG, SHORT_SUMMARY_END_TAG, \
    SHORT_SUMMARY_START_TAG, SUMMARIZE_TAG
from app.inputs import Inputs
from app.tokenizer import get_token_count
from app.bot import Bot
from app.context import commenter, context, ignore_keyword, repo
from app.logger import setup_logger

logger = setup_logger("review")


async def code_review(light_bot: Bot, heavy_bot: Bot, options: Options, prompts: Prompts):
    llm_concurrency_limit = asyncio.Semaphore(options.llm_concurrency_limit)
    github_concurrency_limit = asyncio.Semaphore(options.github_concurrency_limit)

    if context["event_name"] not in ["pull_request", "pull_request_target"]:
        logger.warning(f"Skipped: current event is {context['event_name']}, only support pull_request event")
        return

    if "pull_request" not in context["payload"]:
        logger.warning("Skipped: event data does not contain pull_request")
        return
    else:
        pr_data = context["payload"].get("pull_request")

    inputs = Inputs()
    inputs.title = pr_data.get("title", "")
    if pr_data.get("body"):
        inputs.description = commenter.get_description(pr_data["body"])

    if ignore_keyword in inputs.description:
        logger.info("Skipped: description contains ignore_keyword")
        return

    inputs.system_message = options.system_message

    existing_summarize_cmt = await commenter.find_comment_with_tag(SUMMARIZE_TAG, pr_data["number"])
    existing_commit_ids_block = ""
    existing_summarize_cmt_body = ""
    if existing_summarize_cmt:
        existing_summarize_cmt_body = existing_summarize_cmt.body
        inputs.raw_summary = commenter.get_raw_summary(existing_summarize_cmt_body)
        inputs.short_summary = commenter.get_short_summary(existing_summarize_cmt_body)
        existing_commit_ids_block = commenter.get_reviewed_commit_ids_block(existing_summarize_cmt_body)

    all_commit_ids = await commenter.get_all_commit_ids(pr_data["number"])
    highest_reviewed_commit_id = ""
    if existing_commit_ids_block:
        highest_reviewed_commit_id = commenter.get_highest_reviewed_commit_id(
            all_commit_ids,
            commenter.get_reviewed_commit_ids(existing_commit_ids_block)
        )

    if not highest_reviewed_commit_id or highest_reviewed_commit_id == pr_data["head"]["sha"]:
        logger.info(f"Will review from the base commit: {pr_data['base']['sha']}")
        highest_reviewed_commit_id = pr_data["base"]["sha"]
    else:
        logger.info(f"Will review from commit: {highest_reviewed_commit_id}")

    incremental_diff = repo.compare(highest_reviewed_commit_id, pr_data["head"]["sha"])
    target_branch_diff = repo.compare(pr_data["base"]["sha"], pr_data["head"]["sha"])

    incremental_files = incremental_diff.files
    target_branch_files = target_branch_diff.files

    if incremental_files is None or target_branch_files is None:
        logger.warning("Skipped: files data is missing")
        return

    files = [file for file in target_branch_files if any(
        incremental_file.filename == file.filename for incremental_file in incremental_files
    )]

    if not files:
        logger.warning("Skipped: files is null")
        return

    filter_selected_files = []
    filter_ignored_files = []
    for file in files:
        if not options.check_path(file.filename):
            logger.info(f"skip for excluded path: {file.filename}")
            filter_ignored_files.append(file)
        else:
            filter_selected_files.append(file)

    if not filter_selected_files:
        logger.warning("Skipped: filterSelectedFiles is null")
        return

    commits = incremental_diff.commits

    if not commits:
        logger.warning("Skipped: commits is null")
        return

    async def retrieve_file_contents(file: dict) -> Tuple[str, str, str, List[Tuple[int, int, str]]]:
        file_content_inner = ""
        async with github_concurrency_limit:
            try:
                contents = repo.get_contents(file["filename"], ref=pr_data["base"]["sha"])
                if contents.type == "file" and contents.content:
                    file_content_inner = base64.b64decode(contents.content).decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to get file {file['filename']} contents: {e}. This is OK if it's a new file.")

        file_diff_inner = file.get("patch", "")

        patches = []
        for patch in split_patch(file_diff_inner):
            hunks, patch_lines = parse_patch(patch)
            if not patch_lines:
                continue
            hunks_str = f"""
---new_hunk---
'''
{hunks["new_hunk"]}
'''

---old_hunk---
'''
{hunks["old_hunk"]}
'''
"""
            patches.append((patch_lines["new_hunk"]["start_line"], patch_lines["new_hunk"]["end_line"], hunks_str))

        if patches:
            return file["filename"], file_content_inner, file_diff_inner, patches
        else:
            # Return default values for each part of the tuple
            return file["filename"], file_content_inner, file_diff_inner, []

    async def semaphore_github(file):
        async with github_concurrency_limit:
            return await retrieve_file_contents(file)

    filtered_files = await asyncio.gather(
        *[
            semaphore_github({"filename": file.filename, "patch": file.patch})
            for file in filter_selected_files
        ]
    )

    files_and_changes = [file for file in filtered_files if file is not None]

    if not files_and_changes:
        logger.error("Skipped: no files to review")
        return

    status_msg = f'''<details>
<summary>Commits</summary>
Files that changed from the base of the PR and between {highest_reviewed_commit_id} 
and {pr_data["head"]["sha"]} commits.
</details>
{"" if not files_and_changes else f"""
<details>
<summary>Files selected ({len(files_and_changes)})</summary>

* {chr(10).join([f"{filename} ({len(patches)})" for filename, _, _, patches in files_and_changes])}
</details>
"""}
{"" if not filter_ignored_files else f"""
<details>
<summary>Files ignored due to filter ({len(filter_ignored_files)})</summary>

* {chr(10).join([file.filename for file in filter_ignored_files])}

</details>
"""}
'''

    in_progress_summarize_cmt = commenter.add_in_progress_status(existing_summarize_cmt_body, status_msg)

    await commenter.comment(in_progress_summarize_cmt, SUMMARIZE_TAG, "replace", pr_data["number"])

    summaries_failed = []

    async def do_summary(filename: str, file_content_summary: str, file_diff_summary: str) -> Tuple[str, str, bool]:
        logger.info(f"summarize: {filename}")
        ins = inputs.clone()
        if not file_diff_summary:
            logger.warning(f"summarize: file_diff is empty, skip {filename}")
            summaries_failed.append(f"{filename} (empty diff)")
            return filename, "", False

        ins.filename = filename
        ins.file_diff = file_diff_summary

        summarize_prompt = prompts.render_summarize_file_diff(ins, options.review_simple_changes)
        tokens = get_token_count(summarize_prompt)

        if tokens > options.light_token_limits.request_tokens:
            logger.info(f"summarize: diff tokens exceeds limit, skip {filename}")
            summaries_failed.append(f"{filename} (diff tokens exceeds limit)")
            return filename, "", False

        try:
            summarize_response = await light_bot.chat(summarize_prompt)

            if not summarize_response:
                logger.info("summarize: nothing obtained from llm")
                summaries_failed.append(f"{filename} (nothing obtained from llm)")
                return filename, "", False
            else:
                if not options.review_simple_changes:
                    triage_regex = r"\[TRIAGE\]:\s*(NEEDS_REVIEW|APPROVED)"
                    triage_match = re.search(triage_regex, summarize_response)

                    if triage_match:
                        triage = triage_match.group(1)
                        needs_review = triage == "NEEDS_REVIEW"

                        summary = re.sub(triage_regex, "", summarize_response).strip()
                        logger.info(f"filename: {filename}, triage: {triage}")
                        return filename, summary, needs_review

                return filename, summarize_response, True
        except Exception as e:
            logger.warning(f"summarize: error from llm: {e}")
            summaries_failed.append(f"{filename} (error from llm: {e})")
            return filename, "", False

    summary_promises = []
    skipped_files = []
    for filename, file_content, file_diff, _ in files_and_changes:
        if options.max_files <= 0 or len(summary_promises) < options.max_files:
            async def semaphore_summary(filename, f_content, f_diff):
                async with llm_concurrency_limit:
                    return await do_summary(filename, f_content, f_diff)

            summary_promises.append(
                semaphore_summary(filename, file_content, file_diff)
            )
        else:
            skipped_files.append(filename)

    summaries = [
        summary for summary in await asyncio.gather(*summary_promises)
        if summary is not None
    ]

    if summaries:
        batch_size = 10
        for i in range(0, len(summaries), batch_size):
            summaries_batch = summaries[i:i + batch_size]
            for filename, summary, _ in summaries_batch:
                inputs.raw_summary += f"""---\n{filename}: {summary}\n"""

            # Purpose of this step is to deduplicate and group together all the changes by file:
            summarize_resp = await heavy_bot.chat(prompts.render_summarize_changesets(inputs))
            if not summarize_resp:
                logger.warning("summarize_resp: nothing obtained from llm")
            else:
                inputs.raw_summary = summarize_resp

    summarize_final_response = await heavy_bot.chat(prompts.render_summarize(inputs))
    if not summarize_final_response:
        logger.warning("summarize_final_response: nothing obtained from llm")

    if not options.disable_release_notes:
        release_notes_response = await heavy_bot.chat(prompts.render_summarize_release_notes(inputs))
        if not release_notes_response:
            logger.info("release notes: nothing obtained from llm")
        else:
            message = "### Summary by SeineSailor\n\n" + release_notes_response
            try:
                await commenter.update_description(pr_data["number"], message)
            except Exception as err:
                logger.warning(f"release notes: error from github: {err}")

    summarize_short_response = await heavy_bot.chat(prompts.render_summarize_short(inputs))
    inputs.short_summary = summarize_short_response

    summarize_comment = f"""{summarize_final_response}
{RAW_SUMMARY_START_TAG}
{inputs.raw_summary}
{RAW_SUMMARY_END_TAG}
{SHORT_SUMMARY_START_TAG}
{inputs.short_summary}
{SHORT_SUMMARY_END_TAG}
"""
# ---
#
# <details>
# <summary>Uplevel your code reviews with SeineSailor Pro</summary>
#
# ### SeineSailor Pro
#
# If you like this project, please support us by purchasing the [Pro version](https://SeineSailor.ai).
    # The Pro version has advanced context, superior noise reduction and several proprietary improvements compared to
    # the open source version. Moreover, SeineSailor Pro is free for open source projects.
#
# </details>
# """

    status_msg += f'''
{"" if not skipped_files else f"""
<details>
<summary>Files not processed due to max files limit ({len(skipped_files)})</summary>

* {chr(10).join(skipped_files)}

</details>
"""}
{"" if not summaries_failed else f"""
<details>
<summary>Files not summarized due to errors ({len(summaries_failed)})</summary>

* {chr(10).join(summaries_failed)}

</details>
"""}
'''

    if not options.disable_review:
        files_and_changes_review = [
            (filename, file_content, file_diff, patches)
            for filename, file_content, file_diff, patches in files_and_changes
            if any(summary_filename == filename for summary_filename, _, _ in summaries)
        ]

        reviews_skipped = [
            filename for filename, _, _, _ in files_and_changes
            if filename not in [filename for filename, _, _, _ in files_and_changes_review]
        ]

        reviews_failed = []
        lgtm_count = 0
        review_count = 0

        async def do_review(filename: str, f_content: str, patches: List[Tuple[int, int, str]]):
            nonlocal lgtm_count, review_count
            logger.info(f"reviewing {filename}")
            ins = inputs.clone()
            ins.filename = filename

            tokens = get_token_count(prompts.render_review_file_diff(ins))
            patches_to_pack = 0
            for _, _, patch in patches:
                patch_tokens = get_token_count(patch)
                if tokens + patch_tokens > options.heavy_token_limits.request_tokens:
                    logger.info(
                        f"only packing {patches_to_pack} / {len(patches)} patches, "
                        f"tokens: {tokens} / {options.heavy_token_limits.request_tokens}")
                    break
                tokens += patch_tokens
                patches_to_pack += 1

            patches_packed = 0
            for start_line, end_line, patch in patches:
                if pr_data is None:
                    logger.warning("No pull request found, skipping.")
                    continue

                if patches_packed >= patches_to_pack:
                    logger.info(
                        f"unable to pack more patches into this request, "
                        f"packed: {patches_packed}, total patches: {len(patches)}, skipping.")
                    if options.debug:
                        logger.info(f"prompt so far: {prompts.render_review_file_diff(ins)}")
                    break
                patches_packed += 1

                comment_chain = ""
                try:
                    all_chains = await commenter.get_comment_chains_within_range(
                        pr_data["number"],
                        filename,
                        start_line,
                        end_line,
                        COMMENT_REPLY_TAG
                    )

                    if all_chains:
                        logger.info(f"Found comment chains: {all_chains} for {filename}")
                        comment_chain = all_chains
                except Exception as e:
                    logger.warning(f"Failed to get comments: {e}, skipping.")

                comment_chain_tokens = get_token_count(comment_chain)
                if tokens + comment_chain_tokens > options.heavy_token_limits.request_tokens:
                    comment_chain = ""
                else:
                    tokens += comment_chain_tokens

                ins.patches += f"""
{patch}
"""
                if comment_chain:
                    ins.patches += f"""
---comment_chains---
'''
{comment_chain}
'''
"""
                ins.patches += """
---end_change_section---"""

            if patches_packed > 0:
                try:
                    response = await heavy_bot.chat(prompts.render_review_file_diff(ins))
                    if not response:
                        logger.info("review: nothing obtained from llm")
                        reviews_failed.append(f"{filename} (no response)")
                        return

                    reviews = parse_review(response, patches, options.debug)
                    for review in reviews:
                        if not options.review_comment_lgtm and (
                                "LGTM" in review.comment or "looks good to me" in review.comment):
                            lgtm_count += 1
                            continue

                        if pr_data is None:
                            logger.warning("No pull request found, skipping.")
                            continue

                        try:
                            review_count += 1
                            await commenter.buffer_review_comment(
                                filename,
                                review.start_line,
                                review.end_line,
                                review.comment
                            )
                        except Exception as e:
                            reviews_failed.append(f"{filename} comment failed ({e})")
                except Exception as e:
                    logger.warning(f"Failed to review: {e}, skipping.")
                    reviews_failed.append(f"{filename} ({e})")
            else:
                reviews_skipped.append(f"{filename} (diff too large)")

        review_promises = []
        for filename, file_content, _, patches in files_and_changes_review:
            if options.max_files <= 0 or len(review_promises) < options.max_files:
                async def semaphore_review(filename, f_content, patches):
                    async with llm_concurrency_limit:
                        return await do_review(filename, f_content, patches)

                review_promises.append(
                    semaphore_review(filename, file_content, patches)
                )
            else:
                skipped_files.append(filename)

        await asyncio.gather(*review_promises)

        status_msg += f'''
{"" if not reviews_failed else f"""<details>
<summary>Files not reviewed due to errors ({len(reviews_failed)})</summary>

{chr(10).join(reviews_failed)}

</details>
"""}
{"" if not reviews_skipped else f"""<details>
<summary>Files skipped from review due to trivial changes ({len(reviews_skipped)})</summary>

{chr(10).join(reviews_skipped)}

</details>
"""}
<details>
<summary>Review comments generated ({review_count + lgtm_count})</summary>

Review: {review_count}
LGTM: {lgtm_count}

</details>

<details>
<summary>Tips</summary>
Chat with SeineSailor (@SeineSailor)

Reply on review comments left by this bot to ask follow-up questions. A review comment is a comment on a diff or a file.
Invite the bot into a review comment chain by tagging @SeineSailor in a reply.

Code suggestions

The bot may make code suggestions, 
but please review them carefully before committing since the line number ranges may be misaligned.
You can edit the comment made by the bot and manually tweak the suggestion if it is slightly off.

Pausing incremental reviews

Add @SeineSailor: ignore anywhere in the PR description to pause further reviews from the bot.

</details>
'''
        summarize_comment += f"""\n{commenter.add_reviewed_commit_id(existing_commit_ids_block,
                                                                     pr_data["head"]["sha"])}"""

        await commenter.submit_review(
            pr_data["number"],
            commits[-1].sha,
            status_msg
        )

    await commenter.comment(summarize_comment, SUMMARIZE_TAG, "replace", pr_data["number"])


def split_patch(patch: str) -> List[str]:
    if patch is None:
        return []

    pattern = re.compile(r"(^@@ -(\d+),(\d+) \+(\d+),(\d+) @@).*$", re.MULTILINE)

    result = []
    last = -1
    for match in pattern.finditer(patch):
        if last == -1:
            last = match.start()
        else:
            result.append(patch[last:match.start()])
            last = match.start()

    if last != -1:
        result.append(patch[last:])

    return result


def patch_start_end_line(patch: str) -> Optional[Dict[str, Dict[str, int]]]:
    pattern = re.compile(r"(^@@ -(\d+),(\d+) \+(\d+),(\d+) @@)", re.MULTILINE)
    match = pattern.search(patch)
    if match:
        old_begin = int(match.group(2))
        old_diff = int(match.group(3))
        new_begin = int(match.group(4))
        new_diff = int(match.group(5))
        return {
            "old_hunk": {
                "start_line": old_begin,
                "end_line": old_begin + old_diff - 1
            },
            "new_hunk": {
                "start_line": new_begin,
                "end_line": new_begin + new_diff - 1
            }
        }
    else:
        return {}


def parse_patch(patch: str) -> (dict, dict):
    hunk_info = patch_start_end_line(patch)
    if not hunk_info:
        return {}, {}

    old_hunk_lines = []
    new_hunk_lines = []

    new_line = hunk_info["new_hunk"]["start_line"]

    lines = patch.split("\n")[1:]

    if lines[-1] == "":
        lines.pop()

    skip_start = 3
    skip_end = 3

    current_line = 0

    removal_only = not any(line.startswith("+") for line in lines)

    for line in lines:
        current_line += 1
        if line.startswith("-"):
            old_hunk_lines.append(line[1:])
        elif line.startswith("+"):
            new_hunk_lines.append(f"{new_line}: {line[1:]}")
            new_line += 1
        else:
            old_hunk_lines.append(line)
            if removal_only or (skip_start < current_line <= len(lines) - skip_end):
                new_hunk_lines.append(f"{new_line}: {line}")
            else:
                new_hunk_lines.append(line)
            new_line += 1

    return {
        "old_hunk": "\n".join(old_hunk_lines),
        "new_hunk": "\n".join(new_hunk_lines)
    }, hunk_info


class Review:
    def __init__(self, start_line: int, end_line: int, comment: str):
        self.start_line = start_line
        self.end_line = end_line
        self.comment = comment


def parse_review(response: str, patches: List[Tuple[int, int, str]], debug=False) -> List[Review]:
    reviews = []

    def sanitize_code_block(comment: str, code_block_label: str) -> str:
        code_block_start = f"```{code_block_label}"
        code_block_end = "```"
        line_number_regex = re.compile(r"^ *(\d+): ", re.MULTILINE)

        code_block_start_index = comment.find(code_block_start)

        while code_block_start_index != -1:
            code_block_end_index = comment.find(code_block_end, code_block_start_index + len(code_block_start))

            if code_block_end_index == -1:
                break

            code_block = comment[code_block_start_index + len(code_block_start):code_block_end_index]
            sanitized_block = line_number_regex.sub("", code_block)

            comment = (comment[:code_block_start_index + len(code_block_start)]
                       + sanitized_block + comment[code_block_end_index:])

            code_block_start_index = comment.find(code_block_start,
                                                  code_block_start_index + len(code_block_start) + len(
                                                      sanitized_block) + len(code_block_end))

        return comment

    def sanitize_response(comment: str) -> str:
        comment = sanitize_code_block(comment, "suggestion")
        comment = sanitize_code_block(comment, "diff")
        return comment

    response = sanitize_response(response.strip())

    lines = response.split("\n")
    line_number_range_regex = re.compile(r"(?:^|\s)(\d+)-(\d+):\s*$")
    comment_separator = "---"

    current_start_line = None
    current_end_line = None
    current_comment = ""

    def store_review():
        if current_start_line is not None and current_end_line is not None:
            review = Review(current_start_line, current_end_line, current_comment)

            within_patch = False
            best_patch_start_line = -1
            best_patch_end_line = -1
            max_intersection = 0

            for start_line, end_line, _ in patches:
                intersection_start = max(review.start_line, start_line)
                intersection_end = min(review.end_line, end_line)
                intersection_length = max(0, intersection_end - intersection_start + 1)

                if intersection_length > max_intersection:
                    max_intersection = intersection_length
                    best_patch_start_line = start_line
                    best_patch_end_line = end_line
                    within_patch = intersection_length == review.end_line - review.start_line + 1

                if within_patch:
                    break

            if not within_patch:
                if best_patch_start_line != -1 and best_patch_end_line != -1:
                    review.comment = (f"> Note: This review was outside of the patch, "
                                      f"so it was mapped to the patch with the greatest overlap. "
                                      f"Original lines [{review.start_line}-{review.end_line}]\n\n{review.comment}")
                    review.start_line = best_patch_start_line
                    review.end_line = best_patch_end_line
                else:
                    review.comment = (f"> Note: This review was outside of the patch, "
                                      f"but no patch was found that overlapped with it. "
                                      f"Original lines [{review.start_line}-{review.end_line}]\n\n{review.comment}")
                    review.start_line = patches[0][0]
                    review.end_line = patches[0][1]

            reviews.append(review)

            logger.info(
                f"Stored comment for line range {current_start_line}-{current_end_line}: {current_comment.strip()}")

    for line in lines:
        line_number_range_match = line_number_range_regex.search(line)

        if line_number_range_match:
            store_review()
            current_start_line = int(line_number_range_match.group(1))
            current_end_line = int(line_number_range_match.group(2))
            current_comment = ""
            if debug:
                logger.info(f"Found line number range: {current_start_line}-{current_end_line}")
            continue

        if line.strip() == comment_separator:
            store_review()
            current_start_line = None
            current_end_line = None
            current_comment = ""
            if debug:
                logger.info("Found comment separator")
            continue

        if current_start_line is not None and current_end_line is not None:
            current_comment += f"{line}\n"

    store_review()

    return reviews
