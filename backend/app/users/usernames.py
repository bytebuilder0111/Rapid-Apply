from typing import Annotated

from pydantic import Field

# Letters, digits and . _ - ; no spaces. Case is kept for display, ignored for login.
Username = Annotated[str, Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")]
