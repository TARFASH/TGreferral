import logging
import os
from pathlib import Path

from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter
from dotenv import load_dotenv

# Getting .env variables.
dotenv_path = Path("../config/dev.env")
load_dotenv(dotenv_path=dotenv_path)
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
CHAT_LINK = os.getenv("CHAT_LINK")
# Configure logging
logger = logging.getLogger(__name__)

async def is_private_chat(message: types.Message):
    if message.chat.type != "private":
        return False
    return True

class IsTargetChat(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        if message.chat.id != int(CHAT_ID):
            await message.answer("Эта команда работает только в определённом чате!")
            logger.info(f"Command attempted in wrong chat by @{message.from_user.username} (ID: {message.from_user.id})")
            return False
        return True

class IsAdmin(BaseFilter):
    async def __call__(self, message: types.Message, bot) -> bool:
        try:
            admins = await bot.get_chat_administrators(chat_id=CHAT_ID)
            admin_ids = [admin.user.id for admin in admins]
            if message.from_user.id not in admin_ids:
                await message.answer("Эта команда доступна только администраторам чата!")
                logger.info(f"Non-admin @{message.from_user.username} (ID: {message.from_user.id}) attempted admin command")
                return False
            return True
        except TelegramBadRequest as e:
            await message.answer("Ошибка: убедитесь, что бот имеет права администратора!")
            logger.error(f"Failed to check admin status: {e}")
            return False
