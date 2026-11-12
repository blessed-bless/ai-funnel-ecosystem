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
            [KeyboardButton(text="Оставить заявку"), KeyboardButton(text="Связаться с менеджером")],
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
        "Привет. Я помогу собрать заявку: задача + контакт.\n"
        "Напиши, что нужно автоматизировать, или жми «Оставить заявку».",
        reply_markup=main_keyboard(),
    )


async def handle_manager(message: Message) -> None:
    url = get_settings().telegram_manager_url
    await message.answer(f"Менеджер: {url}\nМожешь написать сюда же — оформлю заявку сам.")


async def handle_text(message: Message) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    if text == "Оставить заявку":
        text = "Хочу оставить заявку на автоматизацию."
    if text == "Связаться с менеджером":
        await handle_manager(message)
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
        suffix = "\n\nЗаявка готова и лежит в CRM (/crm). Менеджер увидит контакт."
    await message.answer(reply + suffix, reply_markup=main_keyboard())


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
