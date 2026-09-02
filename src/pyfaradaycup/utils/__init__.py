"""Package utilities."""

__all__: list[str] = ["placeholder"]

from typing import Literal


def placeholder(x: int) -> Literal[42]:
    """
    Run a placeholder function.

    Examples
    --------
    >>> placeholder(1)  # intentional failure
    43
    """
    return 42
