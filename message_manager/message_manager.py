"""Status message manager for the scheduler."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


def _load_error_definitions() -> dict:
    file_path = Path(__file__).parent / "errors.toml"
    with file_path.open("rb") as f:
        return tomllib.load(f)


# Load error definitions from a TOML file only once
_MESSAGES = _load_error_definitions()


@dataclass(frozen=True)
class StatusMessage:
    """A structure containing a status code and a formatted status message."""

    code: str = ""
    message: str = ""


def get_status_message(key: str, **kwargs: str) -> StatusMessage:
    """Get status code and message for a given key.

    Args:
        key (str): The key for the message.
        **kwargs (str): The keyword arguments to format the message.

    Returns:
        StatusMessage: The status code and message.
    """
    try:
        data = _MESSAGES[key]
        code = data["code"]
        message = data["message"]

        formatted_message = message.format(**kwargs)
    except KeyError:
        return StatusMessage(code="UNKNOWN", message="An unknown error occurred.")

    return StatusMessage(code=code, message=formatted_message)
