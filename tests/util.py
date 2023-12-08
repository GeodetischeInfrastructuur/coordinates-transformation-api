from contextlib import contextmanager
from typing import Optional

import pytest


@contextmanager
def not_raises(exception, message: Optional[str] = ""):
    try:
        yield
    except exception:
        if message != "":
            raise pytest.fail(f"DID RAISE {exception}")  # noqa: B904
        else:
            raise pytest.fail(message.format(exc=exception))  # noqa: B904
