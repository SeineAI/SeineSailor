class Inputs:
    def __init__(
        self,
        system_message: str = "",
        title: str = "no title provided",
        description: str = "no description provided",
        raw_summary: str = "",
        short_summary: str = "",
        filename: str = "",
        file_content: str = "file contents cannot be provided",
        file_diff: str = "file diff cannot be provided",
        patches: str = "",
        diff: str = "no diff",
        comment_chain: str = "no other comments on this patch",
        comment: str = "no comment provided"
    ):
        self.system_message = system_message
        self.title = title
        self.description = description
        self.raw_summary = raw_summary
        self.short_summary = short_summary
        self.filename = filename
        self.file_content = file_content
        self.file_diff = file_diff
        self.patches = patches
        self.diff = diff
        self.comment_chain = comment_chain
        self.comment = comment

    def clone(self):
        return Inputs(
            self.system_message,
            self.title,
            self.description,
            self.raw_summary,
            self.short_summary,
            self.filename,
            self.file_content,
            self.file_diff,
            self.patches,
            self.diff,
            self.comment_chain,
            self.comment
        )

    def render(self, content: str) -> str:
        if not content:
            return ""

        content = content.replace("$system_message", self.system_message)
        content = content.replace("$title", self.title)
        content = content.replace("$description", self.description)
        content = content.replace("$raw_summary", self.raw_summary)
        content = content.replace("$short_summary", self.short_summary)
        content = content.replace("$filename", self.filename)
        content = content.replace("$file_content", self.file_content)
        content = content.replace("$file_diff", self.file_diff)
        content = content.replace("$patches", self.patches)
        content = content.replace("$diff", self.diff)
        content = content.replace("$comment_chain", self.comment_chain)
        content = content.replace("$comment", self.comment)

        return content