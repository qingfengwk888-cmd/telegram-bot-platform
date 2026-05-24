async def dispatch_bot_primary_action_callback(
    *,
    callback_query: dict,
    platform_bot_token: str,
    from_user: dict,
    from_id: int,
    data: str,
    callback_id: str,
    display_name: str,
    bot,
) -> bool:
    from app.services.bot_button_callback_service import try_handle_bot_button_callback
    from app.services.bot_manage_menu_callback_service import try_handle_bot_manage_menu_callback

    if await try_handle_bot_button_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_user=from_user,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        display_name=display_name,
        bot=bot,
    ):
        return True

    if await try_handle_bot_manage_menu_callback(
        callback_query=callback_query,
        platform_bot_token=platform_bot_token,
        from_id=from_id,
        data=data,
        callback_id=callback_id,
        bot=bot,
    ):
        return True

    return False
