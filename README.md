# SeineSailor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/github/last-commit/SeineAI/SeineSailor/main?style=flat-square)](https://github.com/SeineAI/SeineSailor/commits/main)

## Overview

SeineSailor is an AI-powered copilot for project managers, designed to assist with code reviews, project discussions,
and knowledge transfer. It leverages the power of WatsonX's `llama3` and `mixt-8x7B` models to provide intelligent and
context-aware support throughout the development lifecycle.

## Features

- **PR Review and Summarization**: SeineSailor can be summoned to review pull requests and provide a summary of the
  changes when mentioned in a PR comment.
- **Project Discussion Participation**: SeineSailor can actively participate in project discussions and brainstorming
  sessions when invited using the `@SeineSailor` mention in issues or other discussion forums.
- **Knowledge Transfer**: SeineSailor maintains a knowledge base of the project's development history and can assist new
  developers by answering questions about the codebase, architecture, and function implementations.
- **Customizable Prompts**: Tailor the `system_message`, `summarize`, and other prompts to focus on specific aspects of
  the review process or change the review objective.

To use SeineSailor, you need to add the provided YAML file to your repository and configure the required environment
variables, such as `GITHUB_TOKEN` and `WATSONX_API_KEY`. For more information on usage, examples, and contributing,
refer to the sections below.

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
  issue_comment:
    types: [ created ]
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_target:
    types: [opened, synchronize, reopened]
  pull_request_review_comment:
    types: [ created ]
  discussion:
    types: [ created ]

concurrency:
  group:
    ${{ github.repository }}-${{ github.event.number || github.head_ref ||
    github.sha }}-${{ github.workflow }}-${{ github.event_name ==
    'pull_request_review_comment' && 'pr_comment' || 
    github.event_name == 'issue_comment' && 'issue' || 
    github.event_name == 'discussion' && 'discussion' }}
  cancel-in-progress: true
  
jobs:
  seinesailor:
    if: contains(github.event.comment.body, '@SeineSailor')
    runs-on: ubuntu-latest
    steps:
      - uses: SeineAI/SeineSailor@latest
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          IBM_CLOUD_API_KEY: ${{ secrets.IBM_CLOUD_API_KEY }}
          WATSONX_PROJECT_ID: ${{ secrets.WATSONX_PROJECT_ID }}
```

### Environment Variables

- `GITHUB_TOKEN`: This should already be available in the GitHub Action environment. It is used to interact with the
  GitHub API.
- `IBM_CLOUD_API_KEY` and `WATSONX_PROJECT_ID`: Use these to authenticate with the WatsonX API. Please add this key to 
  your GitHub Action secrets.

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

## License

SeineSailor is released under the [MIT License](LICENSE).