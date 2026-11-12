import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from aifunnel.ai import build_ai
from aifunnel.config import get_settings
from aifunnel.db import SessionLocal, init_db
from aifunnel.logging_setup import setup_logging
from aifunnel.services import funnels as funnel_service
from aifunnel.services import leads as lead_service

logger = logging.getLogger("aifunnel.bot")


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Оставить заявку"), KeyboardButton(text="Статус заявки")],
            [KeyboardButton(text="Связаться с менеджером"), KeyboardButton(text="Помощь")],
        ],
        resize_keyboard=True,
    )


async def handle_start(message: Message, command: CommandObject) -> None:
    source = (command.args or get_settings().funnel_default_source).strip() or "direct"
    async with SessionLocal() as session:
        funnel = await funnel_service.ensure_default_funnel(session)
        lead = await lead_service.get_or_create_by_telegram(
            session,
            telegram_id=str(message.from_user.id),
            source=source,
            username=message.from_user.username,
            funnel_id=funnel.id,
        )
        if source and source != "direct" and lead.source != source:
            lead.source = source
            await session.commit()

    await message.answer(
        "Привет. Соберу заявку: задача + контакт.\n"
        "Напиши, что автоматизировать, или жми кнопки ниже.",
        reply_markup=main_keyboard(),
    )


async def handle_manager(message: Message) -> None:
    url = get_settings().telegram_manager_url
    await message.answer(
        f"Менеджер: {url}\n"
        "Можешь продолжить здесь — оформлю заявку и положу в CRM."
    )


async def handle_help(message: Message) -> None:
    await message.answer(
        "<b>Команды</b>\n"
        "/start — начать\n"
        "/status — статус твоей заявки\n"
        "/manager — связь с менеджером\n"
        "/help — эта справка\n\n"
        "Просто напиши задачу и телефон — этого хватит.",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


async def handle_status(message: Message) -> None:
    async with SessionLocal() as session:
        funnel = await funnel_service.ensure_default_funnel(session)
        lead = await lead_service.get_or_create_by_telegram(
            session,
            telegram_id=str(message.from_user.id),
            source=get_settings().funnel_default_source,
            username=message.from_user.username,
            funnel_id=funnel.id,
        )
    await message.answer(
        f"Заявка <code>#{lead.id}</code>\n"
        f"Статус: <b>{lead.status}</b>\n"
        f"Стадия: {lead.stage_slug or '—'}\n"
        f"Score: {lead.score}\n"
        f"Телефон: {lead.phone or 'не указан'}\n"
        f"Нужда: {(lead.need or '—')[:180]}",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )


async def handle_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    if text == "Оставить заявку":
        text = "Хочу оставить заявку на автоматизацию."
    elif text == "Связаться с менеджером":
        await handle_manager(message)
        return
    elif text == "Статус заявки":
        await handle_status(message)
        return
    elif text == "Помощь":
        await handle_help(message)
        return

    settings = get_settings()
    source = settings.funnel_default_source
    async with SessionLocal() as session:
        funnel = await funnel_service.ensure_default_funnel(session)
        lead = await lead_service.get_or_create_by_telegram(
            session,
            telegram_id=str(message.from_user.id),
            source=source,
            username=message.from_user.username,
            funnel_id=funnel.id,
        )
        ai = build_ai()
        lead, reply, ready = await lead_service.chat_with_lead(
            session, ai, lead=lead, message=text
        )

    suffix = ""
    if ready:
        suffix = (
            f"\n\nЗаявка <code>#{lead.id}</code> готова (score {lead.score}). "
            "Менеджер увидит её в CRM."
        )
        await message.answer(reply + suffix, parse_mode="HTML", reply_markup=main_keyboard())
        return
    await message.answer(reply, reply_markup=main_keyboard())


async def _run_async() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN пуст — пропиши его в .env")

    await init_db()
    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_manager, Command("manager"))
    dp.message.register(handle_status, Command("status"))
    dp.message.register(handle_help, Command("help"))
    dp.message.register(handle_text, F.text)

    logger.info("Bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def run() -> None:
    asyncio.run(_run_async())


if __name__ == "__main__":
    run()
