def build_bot_callback_context(*, callback_query: dict) -> dict:
    from_user = callback_query.get("from") or {}
    from_id = int(from_user.get("id") or 0)
    data = callback_query.get("data") or ""
    callback_id = callback_query["id"]

    username = from_user.get("username") or ""
    first_name = from_user.get("first_name") or ""
    last_name = from_user.get("last_name") or ""
    name_text = " ".join([x for x in [first_name, last_name] if x]).strip()
    display_name = f"@{username}" if username else (name_text or f"UID:{from_id}")

    return {
        "from_user": from_user,
        "from_id": from_id,
        "data": data,
        "callback_id": callback_id,
        "username": username,
        "display_name": display_name,
    }
