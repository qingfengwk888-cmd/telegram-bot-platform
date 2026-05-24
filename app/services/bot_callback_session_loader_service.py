async def load_bot_callback_session(
    *,
    from_id: int,
    data: str,
):
    from app.services.apply_service import load_apply_session, clear_apply_session
    from app.services.input_session_service import is_busy_input_session

    session = await load_apply_session(from_id)

    if (
        is_busy_input_session(session)
        and data not in {
            "admin_tenant_broadcast_confirm",
            "admin_tenant_broadcast_cancel",
            "platform_global_broadcast_confirm",
            "platform_global_broadcast_cancel",
            "platform_global_broadcast_target:cancel",
        }
        and (
            data.startswith("platform_ad_menu:")
            or data.startswith("platform_ad_pick:")
            or data.startswith("admin_tenant_broadcast:")
            or data.startswith("admin_tenant_menu:")
            or data.startswith("admin_tenant_sort:")
            or data.startswith("admin_tenant_filter:")
            or data.startswith("admin_tenant_back:")
            or data.startswith("admin_tenant:view:")
        )
    ):
        await clear_apply_session(from_id)
        session = None

    return session
