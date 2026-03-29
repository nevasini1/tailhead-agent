"""Application errors with stable exit-code mapping in the CLI."""


class TrailheadAgentError(Exception):
    """Base error for user-facing failures."""

    exit_code = 1


class ConfigurationError(TrailheadAgentError):
    """Invalid YAML, missing config file, or bad environment."""

    exit_code = 2


class UrlValidationError(TrailheadAgentError):
    """Start URL failed security / format checks."""

    exit_code = 2


class LLMProviderError(TrailheadAgentError):
    """LLM API failures, bad JSON, or missing credentials."""

    exit_code = 3


class OrgExecutorError(TrailheadAgentError):
    """Org / Salesforce CLI integration failures (missing sf, bad alias, deploy error)."""

    exit_code = 2
