import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict
from collections import defaultdict

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from Config import (
    BOT_TOKEN, FORBIDDEN_WORDS, PUNISHMENT_DURATIONS,
    VIOLATION_WINDOW, BLOCKED_MESSAGE_TEMPLATE, GROUP_NOTIFICATION_TEMPLATE, format_duration
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class ModerationBot:


    def __init__(self):
        self.forbidden_words = [word.lower() for word in FORBIDDEN_WORDS]
        self.user_violations = defaultdict(list)
        self.admin_notifications = {}

    def clean_old_violations(self, user_id: int) -> None:
        current_time = time.time()
        self.user_violations[user_id] = [
            timestamp for timestamp in self.user_violations[user_id]
            if current_time - timestamp < VIOLATION_WINDOW
        ]

    def get_violation_count(self, user_id: int) -> int:

        self.clean_old_violations(user_id)
        return len(self.user_violations[user_id])

    def add_violation(self, user_id: int) -> int:

        current_time = time.time()
        self.user_violations[user_id].append(current_time)
        return self.get_violation_count(user_id)

    def get_punishment_duration(self, violation_count: int) -> tuple:

        if violation_count < 4:
            return PUNISHMENT_DURATIONS[violation_count], "restrict"
        else:
            return None, "ban"

    def contains_forbidden_word(self, text: str) -> tuple:

        if not text:
            return False, None

        text_lower = text.lower()
        for word in self.forbidden_words:
            if word in text_lower:
                return True, word
        return False, None

    async def restrict_user(self, chat_id: int, user_id: int, duration: int) -> bool:

        try:
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )

            until_date = datetime.now() + timedelta(seconds=duration)

            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )

            logger.info(f"User {user_id} restricted in chat {chat_id} for {duration} seconds")
            return True

        except TelegramForbiddenError:
            logger.error(f"Failed to restrict user {user_id}: Bot lacks permissions or user is admin")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Bad request when restricting user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error when restricting user {user_id}: {e}")
            return False

    async def ban_user(self, chat_id: int, user_id: int) -> bool:
        try:
            await bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                revoke_messages=True
            )
            logger.info(f"Foydalanuvchi {user_id} guruh {chat_id} dan doimiy ravishda chiqarildi")
            return True
        except TelegramForbiddenError:
            logger.error(
                f"Foydalanuvchi {user_id} ni chiqarib bo‘lmadi: Botda ruxsat yetarli emas yoki foydalanuvchi admin")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Foydalanuvchi {user_id} ni chiqarishda xato: {e}")
            return False
        except Exception as e:
            logger.error(f"Foydalanuvchi {user_id} ni chiqarishda kutilmagan xato: {e}")
            return False

    async def send_private_warning(self, user_id: int, word: str, duration: int, violation_count: int,
                                   action: str) -> bool:

        try:
            if action == "ban":
                message = f"❌ Siz guruhdan chiqarildingiz!\n\n🚫 Sabab: \"{word}\" so'zi taqiqlangan\n📊 Bu sizning {violation_count}-chi buzishingiz edi.\n\nIltimos, guruh qoidalariga rioya qiling."
            else:
                message = BLOCKED_MESSAGE_TEMPLATE.format(
                    word=word,
                    duration=format_duration(duration),
                    count=violation_count
                )

            await bot.send_message(
                chat_id=user_id,
                text=message
            )
            logger.info(f"Warning sent to user {user_id} for word '{word}', violation #{violation_count}")
            return True

        except TelegramForbiddenError:
            logger.error(f"Cannot send message to user {user_id}: User blocked the bot")
            return False
        except Exception as e:
            logger.error(f"Failed to send warning to user {user_id}: {e}")
            return False

    async def send_group_notification(self, chat_id: int, user_id: int, user_name: str, word: str, duration: int,
                                      violation_count: int, action: str) -> None:

        try:
            if action == "ban":
                message = f"🚫 **Foydalanuvchi guruhdan chiqarildi**\n\n👤 Foydalanuvchi: [{user_name}](tg://user?id={user_id}) `#{user_id}`\n🚫 Sabab: \"{word}\" so'zi ishlatildi\n📊 Bu foydalanuvchining {violation_count}-chi buzishi"
            else:
                message = GROUP_NOTIFICATION_TEMPLATE.format(
                    user_name=user_name,
                    user_id=user_id,
                    word=word,
                    duration=format_duration(duration),
                    count=violation_count
                )

            notification_msg = await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="Markdown"
            )

            logger.info(
                f"Group notification sent for user {user_name} (#{user_id}) - word: '{word}', violation #{violation_count}")

            if action != "ban":
                self.admin_notifications[user_id] = {
                    'message_id': notification_msg.message_id,
                    'chat_id': chat_id,
                    'duration': duration,
                    'start_time': time.time()
                }
                asyncio.create_task(self.delete_group_notification_after_unblock(user_id, duration))

        except Exception as e:
            logger.error(f"Failed to send group notification: {e}")

    async def delete_group_notification_after_unblock(self, user_id: int, duration: int) -> None:

        try:
            await asyncio.sleep(duration)

            if user_id in self.admin_notifications:
                notification_data = self.admin_notifications[user_id]

                try:
                    await bot.delete_message(
                        chat_id=notification_data['chat_id'],
                        message_id=notification_data['message_id']
                    )
                    logger.info(f"Deleted group notification message for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to delete group notification for user {user_id}: {e}")

                del self.admin_notifications[user_id]
                logger.info(f"Cleaned up notification for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to delete group notification for user {user_id}: {e}")



moderation_bot = ModerationBot()


@dp.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def handle_group_message(message: Message):


    if not message.text:
        return

    is_forbidden, forbidden_word = moderation_bot.contains_forbidden_word(message.text)
    if is_forbidden:
        if not message.from_user:
            return

        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.full_name or message.from_user.username or f"User {user_id}"

        violation_count = moderation_bot.add_violation(user_id)
        duration, action = moderation_bot.get_punishment_duration(violation_count)

        logger.info(
            f"Forbidden word '{forbidden_word}' detected from user {user_name} ({user_id}) in chat {chat_id}. Violation #{violation_count}")

        try:
            await message.delete()
            logger.info(f"Deleted message from user {user_name}")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

        restriction_success = False
        if action == "ban":
            restriction_success = await moderation_bot.ban_user(chat_id, user_id)
        else:
            restriction_success = await moderation_bot.restrict_user(chat_id, user_id, duration)

        if restriction_success:
            await moderation_bot.send_group_notification(chat_id, user_id, user_name, forbidden_word, duration,
                                                         violation_count, action)
            await moderation_bot.send_private_warning(user_id, forbidden_word, duration, violation_count, action)
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Foydalanuvchi {user_name} taqiqlangan so'z ({forbidden_word}) ishlatdi, lekin jazo qo'llanilmedi (botda ruxsat yetarli emas).",
                parse_mode="Markdown"
            )


@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_private_message(message: Message):

    await message.answer("Bu bot faqat guruhlarda ishlaydi. Meni guruhga qo'shing.")


async def main():

    logger.info("Starting Telegram Moderation Bot...")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())