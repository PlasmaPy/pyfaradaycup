"""Package utilities."""

__all__: list[str] = ["placeholder"]

from typing import Literal


def placeholder() -> Literal[42]:
    """
    Run a placeholder function.

    Examples
    --------
    >>> placeholder()
    42
    """
    return 42
