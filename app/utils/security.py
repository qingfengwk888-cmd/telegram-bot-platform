import re
from typing import Optional

from app.config import INTERNAL_API_KEY

def require_internal_api_key(
    x_api_key: Optional[str],
    authorization: Optional[str],
) -> bool:
    header_key = x_api_key or ""
    if not header_key and authorization:
        m = re.match(r"^Bearer\s+(.+)$", authorization, re.I)
        if m:
            header_key = m.group(1)
    return bool(INTERNAL_API_KEY) and header_key == INTERNAL_API_KEY
