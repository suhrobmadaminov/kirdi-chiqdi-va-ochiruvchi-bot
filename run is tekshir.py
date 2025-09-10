import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot(token='8439767153:AAFtrMEgI_1-mf2RSLYcw3N2vyUT-SY7uO0')
# @AiogramUchunBot
dp = Dispatcher()


@dp.message(Command('start'))
async def start_handler(message: Message):
    """Start komandasi uchun handler!"""
    await message.answer(
        "Assalomu alaykum hurmatli foydalanuvchi!\n"
        "Men guruhlarga qo'shildi degan xabarni va guruhni tark qildi degan xabarni o'chirib turaman.\n"
        "Meni guruhingizga qo'shing va admin qilib qo'ying! Xabarlarni o'chirishga ruxsat bering!  https://t.me/+J0edH4-viw9mMzIy"

    )

@dp.message(Command('help'))
async def help_handler(message: Message):
    """Help komandasi uchun handler!"""
    await message.answer(
        "Bot haqida batafsil ma'lumot\n"
        "Komandalar haqida batafsil ma'lumot\n"
        "Qanday ishlashini yozib chiqasiz\n"
        "Qanday sozlashni yozasiz!\n"
        "Eslatmani yozasiz!"
    )

@dp.message()
async def delete_join_message(message: Message):
    """Yangi a'zo qo'shilish xabarlarini o'chirish handleri!"""
    try:

        if message.new_chat_members:
            await message.delete()
            logging.info(f"Guruh {message.chat.id} da qo'shilish xabari o'chirildi!")

        # Agar kimdir guruhdan chiqib ketgan bo'lsa yoki chiqib ketsa:
        elif message.left_chat_member:
            await message.delete()
            logging.info(f"Guruh {message.chat.id} da chiqib ketish xabari o'chirildi!")

    except Exception as e:
        logging.error(f"Xabarni o'chirishda xatolik yuzaga keldi: {e}")

@dp.chat_member()
async def chat_member_handler(chat_member: ChatMemberUpdated):
    """Chat member o'zgarishlari uchun handler (qo'shimcha)"""
    try:
        old_status = chat_member.old_chat_member.status
        new_status = chat_member.new_chat_member.status

        # Agar kimdir yangi qo'shgilgaan bo'lsa
        if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
            logging.info(f"Yangi a'zo qo'shildi: {chat_member.new_chat_member.user.full_name}")

        # Agar kimdir guruhdan chiqib ketgan bo'lsa
        elif old_status in ['member', 'administrator'] and new_status in ['left', 'kicked']:
            logging.info(f"Guruhdan a'zo chiqib ketdi: {chat_member.new_chat_member.user.full_name}")

    except Exception as e:
        logging.info(f"Chat member handlerda xatolik: {e}")


async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Botni ishga tushurishda xatolik yuzaga keldi {e}")
    finally:
        await bot.session.close()


if __name__ == '__main__':
    print("Bot ishga tushmoqda...")
    asyncio.run(main())
