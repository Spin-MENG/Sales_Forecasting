class BusinessValidationError(Exception):
    """Business-facing validation error with actionable messages."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        super().__init__("\n".join(self.messages))

    def __str__(self):
        lines = ["配置校验未通过："]
        lines.extend(f"- {message}" for message in self.messages)
        return "\n".join(lines)

