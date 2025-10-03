import os
from pathlib import Path

from aiogram import types
from dotenv import load_dotenv


# Getting .env variables.
dotenv_path = Path("../config/dev.env")
load_dotenv(dotenv_path=dotenv_path)
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
CHAT_LINK = os.getenv("CHAT_LINK")

async def is_private_chat(message: types.Message):
    if message.chat.type != "private":
        return False
    return True

async def is_target_chat(message: types.Message):
    if message.chat.id != CHAT_ID:
        await message.answer(f"Эта команда работает только в основном чате! Присоединяйся: {CHAT_LINK}")
        return False
    return True
