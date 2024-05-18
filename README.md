# SeineSailor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/github/last-commit/SeineAI/SeineSailor/main?style=flat-square)](https://github.com/SeineAI/SeineSailor/commits/main)

## Overview

SeineSailor is an AI-powered copilot for project managers, designed to assist with code reviews, project discussions,
and knowledge transfer. It leverages the power of `llama3` and `mixtral-8x7b` models, hosted by Cloud providers such as IBM WatsonX, to provide intelligent
and context-aware support throughout the development lifecycle.

SeineSailor is inspired by many research works [[1](https://www.computer.org/csdl/proceedings-article/issre/2023/159400a647/1RKjp8pPMHu), [2](https://arxiv.org/abs/2312.15698)] and open source projects[[3](https://github.com/anc95/ChatGPT-CodeReview), [4](https://github.com/coderabbitai/ai-pr-reviewer)]

## Features
Here's the content formatted as a Markdown table:

| Feature                          | Description                                                                                                                                                     |
|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **PR Review and Summarization**  | SeineSailor provides AI-powered automated reviews and summaries for pull requests on demand. It analyzes the changes and offers insights to streamline the review process. |
| **Code change suggestions**      | Reviews the changes and provides code change suggestions.                                                                                                        |
| **Project Discussion Participation** | Engage SeineSailor in discussions across various forums including pull request review comments, issues, and discussions by mentioning `@SeineSailor`. It can contribute to brainstorming, provide clarifications, summarize discussions, suggest code changes, etc. |
| **Knowledge Transfer and Query Resolution** | Leverages a comprehensive knowledge base to assist developers with queries about the codebase, architectural design, and specific functionalities, aiding in faster onboarding and information sharing. |
| **Smart review skipping**        | By default, skips in-depth review for simple changes (e.g., typo fixes) and when changes look good for the most part. It can be disabled by setting `review_simple_changes` and `review_comment_lgtm` to `true`. |
| **Customizable prompts**         | Tailor the `system_message`, `summarize`, and `summarize_release_notes` prompts to focus on specific aspects of the review process or even change the review objective. |

## Installation

Add the following file to your repository at `.github/workflows/seinesailor.yml`:

```yaml
name: SeineSailor

permissions:
  contents: read
  pull-requests: write
  issues: write
  discussions: write

on:
  issues:
    types: [ opened ]
  issue_comment:
  discussion:
  discussion_comment:
  pull_request_review_comment:
    types: [ created ]
  pull_request:
  pull_request_target:
    types: [ opened, synchronize, reopened ]

concurrency:
  group:
    ${{ github.repository }}-${{ github.event.number || github.head_ref ||
    github.sha }}-${{ github.workflow }}-${{ github.event_name }}
  cancel-in-progress: true
  
jobs:
  seinesailor:
    if: |
      github.event_name == 'pull_request' ||
      github.event_name == 'pull_request_target' && github.event.pull_request.head.repo.fork ||
      (contains(github.event.comment.body, '@SeineSailor') && (
        github.event_name == 'issue_comment' || 
        github.event_name == 'pull_request_review_comment' ||
        github.event_name == 'discussion_comment')) ||
      (github.event_name == 'issues' && contains(github.event.issue.body, '@SeineSailor')) ||
      (github.event_name == 'discussion' && contains(github.event.discussion.body, '@SeineSailor'))
    runs-on: ubuntu-latest
    steps:
      - name: Check for mention outside of quotes in comments
        id: check_mention
        env:
          COMMENT_BODY: ${{ github.event.comment.body }}
        run: |
          echo "checking for mention outside of quotes and code blocks"
          mention_outside_quotes=false
          in_code_block=false
          while IFS= read -r line; do
            # Check for start or end of a code block
            if [[ "$line" =~ ^\`\`\` ]]; then
              if [[ "$in_code_block" = true ]]; then
                in_code_block=false
              else
                in_code_block=true
              fi
            fi
        
            # Process lines that are not in a code block or quoted
            if [[ "$in_code_block" = false && ! "$line" =~ ^\> ]]; then
              if echo "$line" | grep -q '@SeineSailor'; then
                mention_outside_quotes=true
                break
              fi
            fi
          done <<< "$COMMENT_BODY"
          echo "mention_outside_quotes=$mention_outside_quotes" >> $GITHUB_ENV
      - name: Dump event payload for debug
        run: cat $GITHUB_EVENT_PATH
      - name: Run SeineSailor
        uses: SeineAI/SeineSailor@main # or release version tags
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          IBM_CLOUD_API_KEY: ${{ secrets.IBM_CLOUD_API_KEY }}
          WATSONX_PROJECT_ID: ${{ secrets.WATSONX_PROJECT_ID }}
        with:
          debug: false
```

### Environment Variables

- `GITHUB_TOKEN`: This should already be available in the GitHub Action environment. It is used to interact with the
  GitHub API.
- `IBM_CLOUD_API_KEY` and `WATSONX_PROJECT_ID`: Use these to authenticate with the WatsonX API. Please add this key to
  your GitHub Action secrets.
- `OPENAI_API_KEY`: If you want to use OpenAI models instead. Please add this key to your GitHub Action secrets, and
  set in the last part of yaml:

```yaml
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        with:
          debug: false
          tag: stable
          llm_api_type: openai
          llm_light_model: gpt-3.5-turbo
          llm_heavy_model: gpt-4
          api_base_url: https://api.openai.com/v1
```

## Usage

To summon SeineSailor, simply mention `@SeineSailor` in a comment within a pull request, issue, or discussion.
SeineSailor will analyze the context and provide a response based on its understanding of the codebase and project
history.

## Examples

- Requesting a PR review:
  > @SeineSailor Please review this pull request and provide a summary of the changes.

- Asking for clarification on a function:
  > @SeineSailor Can you explain how the `processData` function works and how it interacts with the rest of the
  codebase?

- Seeking guidance on architecture:
  > @SeineSailor What is the overall architecture of this project? How are the different components interconnected?

## Contributing

Contributions to SeineSailor are welcome! If you have any suggestions, bug reports, or feature requests, please open an
issue on the [GitHub repository](https://github.com/SeineAI/SeineSailor).

Important! Please read [Contributing_README.md](docs/Contributing_README.md) to understand how we separate production 
and development process.

## License

SeineSailor is released under the [MIT License](LICENSE).