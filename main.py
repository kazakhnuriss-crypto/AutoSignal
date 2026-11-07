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
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# CONFIG
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not TOKEN or not OWNER_ID:
    raise RuntimeError("BOT_TOKEN немесе OWNER_ID жоқ!")

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Temporary channel settings
channels = {}


# STATES
class Setup(StatesGroup):
    channel = State()
    word = State()
    url = State()


# MENU
def menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Канал қосу",
                    callback_data="add"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Менің каналдарым",
                    callback_data="list"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Каналды өшіру",
                    callback_data="delete"
                )
            ]
        ]
    )


# START
@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id != OWNER_ID:
        return

    await message.answer(
        "⚙️ AUTO SIGNATURE BOT\n\n"
        "Қош келдің, Creator!",
        reply_markup=menu()
    )


# ADD CHANNEL
@dp.callback_query(F.data == "add")
async def add_channel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID:
        return

    await call.message.answer(
        "📢 Каналдың @username немесе ID жібер:"
    )

    await state.set_state(Setup.channel)
    await call.answer()


# GET CHANNEL
@dp.message(Setup.channel)
async def get_channel(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    await state.update_data(
        channel=message.text.strip()
    )

    await message.answer(
        "✏️ Қандай сөз жазылсын?"
    )

    await state.set_state(Setup.word)


# GET WORD
@dp.message(Setup.word)
async def get_word(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return

    await state.update_data(
        word=message.text.strip()
    )

    await message.answer(
        "🔗 Енді URL сілтемесін жібер:"
    )

    await state.set_state(Setup.url)


# GET URL AND SAVE CHANNEL
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
    channel_input = data["channel"]

    try:
        chat = await bot.get_chat(channel_input)

        member = await bot.get_chat_member(
            chat.id,
            bot.id
        )

        if member.status != "administrator":
            await message.answer(
                "❌ Ботты каналға админ етіп қос!"
            )
            await state.clear()
            return

        channels[str(chat.id)] = {
            "title": chat.title or str(chat.id),
            "word": data["word"],
            "url": url
        }

        await message.answer(
            "✅ КАНАЛ ҚОСЫЛДЫ!\n\n"
            f"📢 {chat.title}\n"
            f"✏️ {data['word']}\n"
            f"🔗 {url}",
            reply_markup=menu()
        )

    except Exception as e:
        await message.answer(
            f"❌ Қате: {e}"
        )

    await state.clear()


# SHOW CHANNELS
@dp.callback_query(F.data == "list")
async def show_channels(call: CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return

    if not channels:
        await call.message.answer(
            "📭 Әзірге канал жоқ."
        )
    else:
        for channel_id, data in channels.items():
            await call.message.answer(
                f"📢 {data['title']}\n"
                f"🆔 {channel_id}\n"
                f"✏️ {data['word']}\n"
                f"🔗 {data['url']}"
            )

    await call.answer()


# DELETE CHANNEL
@dp.callback_query(F.data == "delete")
async def delete_menu(call: CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return

    if not channels:
        await call.message.answer("Каналдар жоқ.")
        await call.answer()
        return

    buttons = []

    for channel_id, data in channels.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {data['title']}",
                callback_data=f"del:{channel_id}"
            )
        ])

    await call.message.answer(
        "Қай каналды өшіреміз?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await call.answer()


@dp.callback_query(F.data.startswith("del:"))
async def delete_channel(call: CallbackQuery):
    if call.from_user.id != OWNER_ID:
        return

    channel_id = call.data.split(":", 1)[1]

    if channel_id in channels:
        del channels[channel_id]
        await call.message.answer("✅ Канал өшірілді.")

    await call.answer()


# AUTOMATIC SIGNATURE
@dp.channel_post()
async def sign_post(message: Message):
    data = channels.get(str(message.chat.id))

    if not data:
        return

    original_text = message.text or message.caption

    if not original_text:
        return

    signature = (
        f'<a href="{escape(data["url"], quote=True)}">'
        f'{escape(data["word"])}</a>'
    )

    new_text = original_text + "\n\n" + signature

    try:
        if message.text:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=new_text,
                parse_mode="HTML"
            )

        elif message.caption:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_text,
                parse_mode="HTML"
            )

    except Exception:
        logging.exception("Post editing error")


# RUN
async def main():
    logging.basicConfig(level=logging.INFO)

    dp.include_router(dp.sub_routers[0]) if False else None

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
