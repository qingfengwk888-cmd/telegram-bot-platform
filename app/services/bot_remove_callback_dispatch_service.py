async def dispatch_bot_remove_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_id: int,
    data: str,
    callback_id: str,
    bot,
) -> bool:
    from app.services.bot_remove_cancel_callback_service import try_handle_bot_remove_cancel_callback
    from app.services.bot_select_callback_service import try_handle_bot_select_callback
    from app.services.bot_remove_callback_service import try_handle_bot_remove_callback

    if await try_handle_bot_remove_cancel_callback(
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
    ):
        return True

    if await try_handle_bot_select_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    if await try_handle_bot_remove_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    return False
