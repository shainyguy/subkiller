"""Регистрация всех роутеров."""

from aiogram import Router


def setup_routers() -> Router:
    """Собрать все роутеры в один."""
    from bot.handlers.start import router as start_router
    from bot.handlers.subscriptions import router as subs_router
    from bot.handlers.parse_messages import router as parse_router
    from bot.handlers.pain_counter import router as pain_router
    from bot.handlers.analytics import router as analytics_router
    from bot.handlers.investments import router as invest_router
    from bot.handlers.dna_profile import router as dna_router
    from bot.handlers.alternatives import router as alt_router
    from bot.handlers.leaderboard import router as leader_router
    from bot.handlers.referral import router as ref_router
    from bot.handlers.premium import router as premium_router
    from bot.handlers.trial_sniper import router as trial_router
    from bot.handlers.notifications import router as notif_router
    from bot.handlers.social_proof import router as social_router
    from bot.handlers.weekly_report import router as report_router

    main_router = Router()

    main_router.include_router(start_router)
    main_router.include_router(subs_router)
    main_router.include_router(parse_router)
    main_router.include_router(pain_router)
    main_router.include_router(analytics_router)
    main_router.include_router(invest_router)
    main_router.include_router(dna_router)
    main_router.include_router(alt_router)
    main_router.include_router(leader_router)
    main_router.include_router(ref_router)
    main_router.include_router(premium_router)
    main_router.include_router(trial_router)
    main_router.include_router(notif_router)
    main_router.include_router(social_router)
    main_router.include_router(report_router)

    return main_router