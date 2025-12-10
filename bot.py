import logging
import asyncio
import io
import os
import barcode
from barcode.writer import ImageWriter
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command, CommandObject
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from db import Database
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
BARMEN_IDS = set(
    int(x) for x in os.getenv("BARMEN_IDS", "").split(",") if x.strip()
)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
db = Database()
db.create_tables()


def generate_barcode_image(code: str) -> io.BytesIO:
    CODE128 = barcode.get_barcode_class('code128')
    barcode_obj = CODE128(code, writer=ImageWriter())
    img_bytes = io.BytesIO()
    barcode_obj.write(img_bytes)
    img_bytes.seek(0)
    barcode_file = BufferedInputFile(
        img_bytes.getvalue(),
        filename=f"{code}.png"
    )
    return barcode_file


async def is_member(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["creator", "administrator", "member", "restricted"]
    except TelegramBadRequest:
        return False


async def send_promo(message, user_id: int):
    promo_code = db.create_promo_code(user_id)
    barcode_file = generate_barcode_image(promo_code)
    await message.answer(f"💚 Благодарим!\nПолучите ваш сэндвич по промокоду:")
    await message.answer(f"{promo_code}")
    await message.answer_photo(barcode_file)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id

    if db.has_promo_code(user_id):
        return

    if await is_member(user_id):
        await send_promo(message, user_id)
    else:
        check_btn = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Получить промокод", callback_data="check_sub")]]
        )
        await message.answer(f"Сэндвич-бар BIGBI {CHANNEL_ID}"                             
                             f"\n\nВ канале мы публикуем для вас новинки, скидки и другие акции."
                             f"\n\nПрисоединяйтесь к Bigbi и возьмите любой сэндвич в подарок! 🎁",
                             reply_markup=check_btn)


@dp.callback_query(lambda c: c.data == "check_sub")
async def check_subscription(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if db.has_promo_code(user_id):
        return

    if await is_member(user_id):
        await send_promo(callback_query.message, user_id)
    else:
        await callback_query.answer("Вы не подписаны 😔", show_alert=True)

    await callback_query.answer()


class BarmenStates(StatesGroup):
    checking = State()


@dp.message(Command("bar"))
async def toggle_barmen_mode(message: Message, state: FSMContext):
    if message.from_user.id not in BARMEN_IDS:
        return

    current_state = await state.get_state()
    if current_state == BarmenStates.checking:
        await state.clear()
        await message.answer("Режим бармена выключен 🫡")
    else:
        await state.set_state(BarmenStates.checking)
        await message.answer("Режим бармена включён 🫡")


@dp.message(BarmenStates.checking, Command(commands=["count"]))
async def check_promo_codes_count(message: Message):
    used_count, unused_count = db.count_promo_codes()
    msg = f"{used_count} использовано\n{unused_count} актуально"
    await message.answer(msg)


@dp.message(BarmenStates.checking, Command(commands=["cu"]))
async def check_subscription_cmd(
    message: Message,
    command: CommandObject,
):
    if message.from_user.id not in BARMEN_IDS:
        return

    args = command.args
    if not args or not args.isdigit():
        await message.answer("Использование: /cu <user_id>")
        return

    user_id = int(args)
    msg_parts = [str(user_id), "🟢 Подписан" if await is_member(user_id) else "🔴 Не подписан"]
    msg = "\n".join(msg_parts)
    await message.answer(msg)


@dp.message(BarmenStates.checking, Command(commands=["get_db"]))
async def send_db_file(message: Message):
    if message.from_user.id not in BARMEN_IDS:
        return

    db_path = "promo_codes.db"

    try:
        file = FSInputFile(db_path)
        await message.answer_document(file)
    except Exception as e:
        await message.answer(f"Ошибка при отправке файла: {e}")


@dp.message(BarmenStates.checking)
async def check_promo(message: Message):
    if message.from_user.id not in BARMEN_IDS:
        return

    if not message.text:
        return

    promo_code = message.text.strip().upper()
    record = db.check_promo_code(promo_code)

    if not record:
        await message.answer(f"🔴 Промокод {promo_code} не найден.")
        return

    user = message.from_user
    msg_parts = [promo_code]
    msg_parts += [x for x in (user.username, user.full_name) if x]
    if msg_parts:
        msg_parts[-1] += "\n"

    is_used = record["used"]
    is_subscribed = await is_member(record["user_id"])
    msg_parts.append("🔴 Использован" if is_used else "🟢 Актуален")
    msg_parts.append("🟢 Подписан" if is_subscribed else "🔴 Не подписан")
    if is_subscribed and not is_used:
        msg_parts.append("🟢 Выдать сэндвич!")
        db.mark_used(promo_code)

    msg = "\n".join(msg_parts)
    await message.answer(msg)


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
