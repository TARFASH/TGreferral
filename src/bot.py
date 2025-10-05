import asyncio
import logging
import os
from pathlib import Path

import aiogram.exceptions
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from src.db import save_invite_link, get_invite_link_by_url, save_invited_user, get_recent_invited_users_by_inviter, \
    get_count_invited_by_inviter, get_top_inviters, calculate_debt, mark_rewards_issued
from src.filters import IsTargetChat, IsAdmin

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Getting .env variables.
dotenv_path = Path("../config/dev.env")
load_dotenv(dotenv_path=dotenv_path)
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHAT_LINK = os.getenv("CHAT_LINK")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: types.Message):
    await message.answer(
        'Привет, я реферальный бот "Как-то вот так" чата! '
        f'Присоединяйся к чату! {CHAT_LINK}',
        reply_markup=None
    )
    logger.info(f'Processed /start for user @{message.from_user.username} in PM')


@dp.message(Command("get_link"), IsTargetChat())
async def get_link_handler(message: types.Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        existing_link = save_invite_link(user_id=user_id, invite_link=None, username=username)
        if existing_link and existing_link != "":
            await message.answer(f"Твоя ссылка для приглашения в чат:\n{existing_link}")
            logger.info(f"Retrieved existing invite link for user {username} (ID: {user_id}): {existing_link}")
            return
        invite_link = await bot.create_chat_invite_link(
            chat_id=CHAT_ID,
            name=f"invite by @{username}",
            expire_date=None,
            member_limit=None
        )
        saved_link = save_invite_link(user_id=user_id, invite_link=invite_link.invite_link, username=username)
        await message.answer(f"Вот твоя ссылка для приглашения в чат:\n{saved_link}")
        logger.info(f"Generated invite link for user @{username} (ID: {user_id}): {saved_link}")
    except aiogram.exceptions.TelegramBadRequest:
        await message.answer(
            'Не удалось создать ссылку. Убедись, что бот является администратором чата с правом "Управление ссылками"!'
        )


@dp.message(Command("my_stats"))
async def my_stats_handler(message: types.Message):
    inviter_user_id = message.from_user.id
    recent_invited = get_recent_invited_users_by_inviter(inviter_user_id=inviter_user_id)
    invite_count = get_count_invited_by_inviter(inviter_user_id=inviter_user_id)
    username = message.from_user.username or message.from_user.first_name
    response = (f"🫅🏻@{username}\n"
                f"Вы пригласили человек: {invite_count}\n"
                f"Последние приглашённые:\n")
    for user_counter in range(len(recent_invited)):
        response += f"{user_counter + 1}. <a href='tg://openmessage?user_id={recent_invited[user_counter][0]}'>{recent_invited[user_counter][1]}</a>\n"
    await message.answer(response, parse_mode=ParseMode.HTML)
    logger.info(f"Processed /my_stats for user @{username} (ID: {inviter_user_id}): {invite_count} invited, "
                f"{len(recent_invited)} recent users")


@dp.message(Command("invites_rating"))
async def invites_rating_handler(message: types.Message):
    inviters = get_top_inviters()
    result = "🔗 Топ 20 игроков по приглашениям:\n\n"
    count = 1
    for inviter in inviters:
        result += (f"{count}. <a href='tg://openmessage?user_id={inviters[inviter][0]}'>{inviter}</a> "
                   f"- {inviters[inviter][1]}🤵🏻\n")
        count += 1
    await message.answer(result, parse_mode=ParseMode.HTML)
    logger.info(
        f"Successfully processed /invites_rating. Called {message.from_user.username} (ID: {message.from_user.id}).")


@dp.message(Command("check_debt"), F.reply_to_message, IsTargetChat(), IsAdmin())
async def check_debt_handler(message: types.Message):
    # Get the replied-to user's ID
    target_user = message.reply_to_message.from_user
    target_user_id = target_user.id
    target_username = target_user.username or target_user.first_name

    # Check if the target user exists in the database
    invite_count = get_count_invited_by_inviter(target_user_id)
    debt = calculate_debt(target_user_id)

    response = f"📊 Долг по наградам для @{target_username} (ID: {target_user_id}):\n{debt}"
    await message.answer(response, parse_mode=ParseMode.HTML)
    logger.info(f"Processed /check_debt for user @{target_username} (ID: {target_user_id}) by admin "
                f"@{message.from_user.username} (ID: {message.from_user.id}): {invite_count} invited")


@dp.message(Command("mark_rewards"), F.reply_to_message, IsTargetChat(), IsAdmin())
async def mark_rewards_handler(message: types.Message):
    # Get the replied-to user's ID
    target_user = message.reply_to_message.from_user
    target_user_id = target_user.id
    target_username = target_user.username or target_user.first_name

    # Mark rewards as issued
    result = mark_rewards_issued(target_user_id)

    # Prepare response
    response = f"✅ Награды для @{target_username} (ID: {target_user_id}) отмечены как выданные:\n"
    if result["new_milestones"]:
        response += "\nНовые выданные достижения:\n" + "\n".join(f"- {m}" for m in result["new_milestones"])
    if result["new_extra"] > 0:
        response += f"\nДополнительно за приглашения: {result['new_extra']}💰"
    if not result["new_milestones"] and result["new_extra"] == 0:
        response += "Нет новых наград для выдачи."
    response += f"\n\nИтого: {result['total_flower']}🌸; {result['total_money']}💰"
    if result["vip_status"]:
        response += f"; {result['vip_status']}"

    await message.answer(response, parse_mode=ParseMode.HTML)
    logger.info(f"Processed /mark_rewards for user @{target_username} (ID: {target_user_id}) by admin "
                f"@{message.from_user.username} (ID: {message.from_user.id}): "
                f"New milestones: {result['new_milestones']}, Extra: {result['new_extra']}")


@dp.chat_member()
async def chat_member_handler(update: types.ChatMemberUpdated):
    if update.new_chat_member.status == "member":
        invited_user_id = update.new_chat_member.user.id
        invited_username = update.new_chat_member.user.username or update.new_chat_member.user.first_name
        invite_link = update.invite_link.invite_link if update.invite_link else None
        if invite_link:
            link = get_invite_link_by_url(invite_link)
            if link:
                save_invited_user(
                    inviter_user_id=link.user_id,
                    invited_user_id=invited_user_id,
                    invited_username=invited_username
                )
                logger.info(f"User @{invited_username} (ID: {invited_user_id}) joined via invite by user "
                            f"ID {link.user_id}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
