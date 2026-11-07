
import os
import asyncio
import logging
from html import escape
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not TOKEN or not OWNER_ID:
    raise RuntimeError("BOT_TOKEN немесе OWNER_ID жоқ!")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Канал баптаулары (RAM)
channels = {}

class Setup(StatesGroup):
    channel = State()
    word = State()
    url = State()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Канал қосу",
            callback_data="add"
        )],
        [InlineKeyboardButton(
            text="📋 Менің каналдарым",
            callback_data="list"
        )]
    ])

@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    await message.answer(
        "⚙️ AUTO SIGNATURE BOT\n\nCreator Panel",
        reply_markup=menu()
    )

@dp.callback_query(F.data == "add")
async def add(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID:
        return

    await call.message.answer(
        "📢 Каналдың @username немесе ID жібер:"
    )
    await state.set_state(Setup.channel)
    await call.answer()

@dp.message(Setup.channel)
async def get_channel(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    await state.update_data(channel=message.text.strip())
    await message.answer("✏️ Қандай сөз жазылсын?")
    await state.set_state(Setup.word)

@dp.message(Setup.word)
async def get_word(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    await state.update_data(word=message.text.strip())
    await message.answer("🔗 URL сілтемесін жібер:")
    await state.set_state(Setup.url)

@dp.message(Setup.url)
async def get_url(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    url = message.text.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await message.answer("❌ Дұрыс URL жібер!")
        return

    data = await state.get_data()
    channel = data["channel"]

    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, bot.id)

        if member.status != "administrator":
            await message.answer(
                "❌ Алдымен ботты каналға админ қыл!"
            )
            await state.clear()
            return

        channels[str(chat.id)] = {
            "title": chat.title,
            "word": data["word"],
            "url": url
        }

        await message.answer(
            f"✅ Канал қосылды!\n\n"
            f"📢 {chat.title}\n"
            f"✏️ {data['word']}\n"
            f"🔗 {url}",
            reply_markup=menu()
        )

    except Exception as e:
        await message.answer(
            f"❌ Каналды қосу мүмкін болмады.\n{e}"
        )

    await state.clear()

@dp.callback_query(F.data == "list")
async def show_channels(call: CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return

    if not channels:
        await call.message.answer("Каналдар әлі қосылмаған.")
    else:
        for channel_id, data in channels.items():
            await call.message.answer(
                f"📢 {data['title']}\n"
                f"ID: {channel_id}\n"
                f"Сөз: {data['word']}\n"
                f"URL: {data['url']}"
            )

    await call.answer()

@dp.channel_post()
async def sign_post(message: Message):
    data = channels.get(str(message.chat.id))

    if not data or not message.text:
        return

    if message.text.startswith("/"):
        return

    signature = (
        f'<a href="{escape(data["url"], quote=True)}">'
        f'{escape(data["word"])}</a>'
    )

    new_text = message.text + "\n\n" + signature

    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=new_text,
            parse_mode="HTML",
            entities=None
        )
    except Exception:
        logging.exception("Постты өңдеу қатесі")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
