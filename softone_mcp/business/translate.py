"""
Business-layer translation helpers.

The goal is to keep the business layer consistent and avoid duplicating
SoftOne error-code branching logic across many modules.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from softone_wrapper.domain.errors import SoftOneError

from .constants import SOFTONE_NOT_FOUND_CODE

T = TypeVar("T")


def translate_softone_not_found(
    call: Callable[[], T],
    *,
    exc_factory: Callable[[], Exception],
) -> T:
    """
    Run `call()` and translate SoftOne's not-found error (code 2001)
    into a domain exception created by `exc_factory`.
    """
    try:
        return call()
    except SoftOneError as e:
        if e.code == SOFTONE_NOT_FOUND_CODE:
            raise exc_factory() from e
        raise

