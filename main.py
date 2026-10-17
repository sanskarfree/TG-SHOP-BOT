import asyncio
import random
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- CONFIG ---
BOT_TOKEN = "8678655741:AAGIoE-eMbDDsw7LQjNVULQGgKlHVCccpEs"
OWNER_ID = 8468468528
CHANNEL_ID = "@sanskarmods1"
CHANNEL_LINK = "https://t.me/sanskarmods1"

# --- LOGGING & BOT SETUP ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, is_verified INTEGER DEFAULT 0)")
    cursor.execute("CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, phone TEXT, price REAL, sold INTEGER DEFAULT 0)")
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def verify_user(user_id):
    conn = sqlite3.connect("bot.db")
    conn.execute("UPDATE users SET is_verified=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# --- FSM STATES ---
class VerifyState(StatesGroup):
    waiting_for_answer = State()

class AdminState(StatesGroup):
    waiting_for_stock = State()

# --- CHECK JOIN ---
async def check_join(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking join: {e}")
        return False

# --- PREMIUM KEYBOARDS ---
def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 ʙᴜʏ ᴀᴄᴄᴏᴜɴᴛ", callback_data="buy")
    builder.button(text="📦 ᴍʏ ᴏʀᴅᴇʀꜱ", callback_data="orders")
    builder.button(text="👤 ᴘʀᴏꜰɪʟᴇ", callback_data="profile")
    builder.button(text="💳 ᴡᴀʟʟᴇᴛ", callback_data="wallet")
    builder.button(text="💬 ꜱᴜᴘᴘᴏʀᴛ", callback_data="support")
    builder.adjust(1, 2, 2)
    return builder.as_markup()

def join_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=CHANNEL_LINK)
    builder.button(text="✅ ᴠᴇʀɪꜰʏ", callback_data="check_join")
    builder.adjust(1, 1)
    return builder.as_markup()

def verify_kb(correct_answer):
    builder = InlineKeyboardBuilder()
    options = [correct_answer]
    while len(options) < 4:
        wrong = correct_answer + random.randint(-5, 5)
        if wrong != correct_answer and wrong not in options and wrong > 0:
            options.append(wrong)
    random.shuffle(options)
    for opt in options:
        builder.button(text=str(opt), callback_data=f"ans_{opt}")
    builder.adjust(2, 2)
    return builder.as_markup()

def back_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu")
    return builder.as_markup()

def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 ᴀᴅᴅ ꜱᴛᴏᴄᴋ", callback_data="admin_add_stock")
    builder.button(text="👥 ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ", callback_data="admin_users")
    builder.button(text="🔙 ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- HANDLERS ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    await state.clear()
    
    # Admin ko alert bhejna ki naya user aaya (sirf pehli baar)
    if user[2] == 0:
        await bot.send_message(
            OWNER_ID, 
            f"🚨 <b>New User Alert!</b>\n\n"
            f"Name: {message.from_user.first_name}\n"
            f"Username: @{message.from_user.username or 'None'}\n"
            f"ID: <code>{user_id}</code>",
            parse_mode="HTML"
        )

    if not await check_join(user_id):
        await message.answer(
            f"<b>🔒 ᴄʜᴀɴɴᴇʟ ᴍᴇᴍʙᴇʀꜱʜɪᴘ ʀᴇQᴜɪʀᴇᴅ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Join to continue using the store.</i>\n\n"
            f"Tap Join below and then Verify.",
            reply_markup=join_kb(),
            parse_mode="HTML"
        )
        return

    if user[2] == 0:
        num1 = random.randint(10, 30)
        num2 = random.randint(5, 20)
        correct = num1 + num2
        await state.update_data(correct_answer=correct)
        await state.set_state(VerifyState.waiting_for_answer)
        
        await message.answer(
            f"<b>🛡 ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Quick check to keep bots out.\n\n"
            f"<code>{num1} + {num2} = ?</code>\n\n"
            f"<i>Choose the correct answer below.</i>",
            reply_markup=verify_kb(correct),
            parse_mode="HTML"
        )
        return

    await send_main_menu(message, user_id)

async def send_main_menu(message, user_id):
    user = get_user(user_id)
    balance = user[1]
    await message.answer(
        f"<b>ᴛɢ ᴍᴀɴᴅɪ — ᴀᴄᴄᴏᴜɴᴛ ꜱᴛᴏʀᴇ</b>\n"
        f"<i>ᴘʀᴇᴍɪᴜᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴄᴄᴏᴜɴᴛꜱ</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome, <b>{message.from_user.first_name}</b>\n\n"
        f"<blockquote>🆔 <b>USER ID :</b> <code>{user_id}</code>\n"
        f"💰 <b>BALANCE :</b> ₹{balance:.2f}</blockquote>\n\n"
        f"<i>Browse and purchase verified accounts.</i>\n"
        f"⚡ Instant delivery • 24/7 support",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_join")
async def cb_check_join(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await check_join(user_id):
        await callback.message.delete()
        await start_cmd(callback.message, state)
    else:
        await callback.answer("❌ You haven't joined the channel yet!", show_alert=True)

@dp.callback_query(F.data.startswith("ans_"))
async def cb_verify(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    correct = data.get("correct_answer")
    user_ans = int(callback.data.split("_")[1])
    
    if user_ans == correct:
        verify_user(callback.from_user.id)
        await state.clear()
        await callback.message.delete()
        await callback.message.answer("✅ <b>Verified successfully!</b>", parse_mode="HTML")
        await send_main_menu(callback.message, callback.from_user.id)
    else:
        await callback.answer("❌ Wrong answer. Try again.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"<b>👤 ᴘʀᴏꜰɪʟᴇ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Name: <b>{callback.from_user.first_name}</b>\n"
        f"Username: @{callback.from_user.username or 'None'}\n"
        f"ID: <code>{callback.from_user.id}</code>\n"
        f"Balance: <b>₹{user[1]:.2f}</b>",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "wallet")
async def cb_wallet(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ ᴀᴅᴅ ꜰᴜɴᴅꜱ", callback_data="add_funds")
    builder.button(text="📜 ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴꜱ", callback_data="transactions")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"<b>💳 ᴡᴀʟʟᴇᴛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>Balance: <b>₹{user[1]:.2f}</b>\n"
        f"Deposited: <b>₹0.00</b>\n"
        f"Spent: <b>₹0.00</b></blockquote>\n\n"
        f"<i>Add funds to purchase accounts instantly.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"<b>ᴛɢ ᴍᴀɴᴅɪ — ᴀᴄᴄᴏᴜɴᴛ ꜱᴛᴏʀᴇ</b>\n"
        f"<i>ᴘʀᴇᴍɪᴜᴍ ᴛᴇʟᴇɢʀᴀᴍ ᴀᴄᴄᴏᴜɴᴛꜱ</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome, <b>{callback.from_user.first_name}</b>\n\n"
        f"<blockquote>🆔 <b>USER ID :</b> <code>{callback.from_user.id}</code>\n"
        f"💰 <b>BALANCE :</b> ₹{user[1]:.2f}</blockquote>\n\n"
        f"<i>Browse and purchase verified accounts.</i>\n"
        f"⚡ Instant delivery • 24/7 support",
        reply_markup=main_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.in_({"buy", "orders", "support", "add_funds", "transactions"}))
async def cb_placeholder(callback: types.CallbackQuery):
    await callback.answer("Ye feature next update mein add hoga, Dotbhai!", show_alert=True)

# --- ADMIN COMMANDS ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        f"<b>⚙️ ᴏᴡɴᴇʀ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Welcome, <b>Owner</b>. Select an option below:\n"
        f"<i>(Only visible to you)</i>",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_add_stock")
async def cb_admin_stock(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await callback.message.edit_text(
        "<b>📦 ADD STOCK</b>\n\n"
        "Format mein likh ke bhej:\n"
        "<code>Country | Phone | Price</code>\n\n"
        "<b>Example:</b>\n"
        "<code>India | +919876543210 | 50</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_stock)
    await callback.answer()

@dp.message(AdminState.waiting_for_stock)
async def process_stock(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    try:
        data = message.text.split("|")
        country = data[0].strip()
        phone = data[1].strip()
        price = float(data[2].strip())

        conn = sqlite3.connect("bot.db")
        conn.execute("INSERT INTO stock (country, phone, price) VALUES (?, ?, ?)", (country, phone, price))
        conn.commit()
        conn.close()

        await message.answer("✅ <b>Stock added successfully!</b>", parse_mode="HTML")
        await state.clear()
        
        # Wapas admin panel dikhao
        await message.answer("⚙️ Admin Panel:", reply_markup=admin_menu_kb())
    except Exception:
        await message.answer("❌ Format galat hai. Wapas try kar:\n<code>India | +919876543210 | 50</code>", parse_mode="HTML")

@dp.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()

    await callback.answer(f"Total Registered Users: {count}", show_alert=True)

async def main():
    init_db()
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
