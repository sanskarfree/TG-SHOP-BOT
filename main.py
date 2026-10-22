import asyncio
import random
import sqlite3
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- CONFIG ---
BOT_TOKEN = "8678655741:AAH1KhnvNstm3oocNYfZG1AxK0fyfFNqsno"
OWNER_ID = 8468468528
DEFAULT_CHANNEL_ID = "@sanskarmods1"
SUPPORT_USERNAME = "@sanskarfree"
UPI_ID = "9479380180@fam"
UPI_NAME = "TG MANDI"
MIN_DEPOSIT = 10
MAX_DEPOSIT = 2000
REFER_BONUS = 5.0

# --- API CONFIG (TGMandi API) ---
API_BASE_URL = "https://tgmandi.myvipsite.fun/api/v1"
API_KEY = "tgm_c3a8df4a4e5d3ab62cf16186cfa57ac37ec036a7"
HEADERS = {"X-Api-Key": API_KEY}

# --- LOGGING & BOT SETUP ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, is_verified INTEGER DEFAULT 0, refer_by INTEGER DEFAULT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS api_stock (id TEXT PRIMARY KEY, country_code TEXT, country_name TEXT, price REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, phone TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, note TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_id', ?)", (DEFAULT_CHANNEL_ID,))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('refer_bonus', '5')")
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect("bot.db")
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
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

# --- API FUNCTIONS ---
async def fetch_api_countries():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_BASE_URL}/countries", headers=HEADERS) as resp:
                data = await resp.json()
                return data.get("data", {}).get("countries", [])
        except:
            return []

async def fetch_api_accounts(country_code):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_BASE_URL}/accounts?country={country_code}", headers=HEADERS) as resp:
                data = await resp.json()
                return data.get("data", {}).get("items", [])
        except:
            return []

async def buy_api_account(account_id, max_price):
    async with aiohttp.ClientSession() as session:
        try:
            payload = {"max_price": max_price}
            async with session.post(f"{API_BASE_URL}/accounts/{account_id}/buy", headers=HEADERS, json=payload) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data.get("data", {}).get("order", {})
                return None
        except:
            return None

# --- FSM STATES ---
class VerifyState(StatesGroup):
    waiting_for_answer = State()

class AdminState(StatesGroup):
    waiting_for_channel = State()
    waiting_for_broadcast = State()
    waiting_for_user_balance = State()
    waiting_for_refer_bonus = State()

class WalletState(StatesGroup):
    waiting_for_deposit_amount = State()
    waiting_for_utr = State()

class SearchState(StatesGroup):
    waiting_for_country = State()

# --- CHECK JOIN ---
async def check_join(user_id):
    channel_id = get_setting("channel_id")
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        return False

# --- PREMIUM KEYBOARDS ---
def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 ʙᴜʏ ᴀᴄᴄᴏᴜɴᴛ", callback_data="buy", style="success")
    builder.button(text="📦 ᴍʏ ᴏʀᴅᴇʀꜱ", callback_data="orders", style="primary")
    builder.button(text="👤 ᴘʀᴏꜰɪʟᴇ", callback_data="profile", style="primary")
    builder.button(text="💳 ᴡᴀʟʟᴇᴛ", callback_data="wallet", style="danger")
    builder.button(text="🎁 ʀᴇꜰᴇʀ & ᴇᴀʀɴ", callback_data="refer", style="success")
    builder.button(text="💬 ꜱᴜᴘᴘᴏʀᴛ", callback_data="support", style="primary")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def join_kb():
    channel_id = get_setting("channel_id")
    channel_link = f"https://t.me/{channel_id.replace('@', '')}"
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ", url=channel_link, style="primary")
    builder.button(text="✅ ᴠᴇʀɪꜰʏ", callback_data="check_join", style="success")
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
        builder.button(text=str(opt), callback_data=f"ans_{opt}", style="primary")
    builder.adjust(2, 2)
    return builder.as_markup()

def back_kb(data="main_menu"):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data=data, style="danger")
    return builder.as_markup()

def admin_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 ꜱʏɴᴄ ᴀᴘɪ ꜱᴛᴏᴄᴋ", callback_data="admin_sync_api", style="success")
    builder.button(text="📢 ᴄʜᴀɴɴᴇʟ ᴍᴀɴᴀɢᴇʀ", callback_data="admin_channel", style="primary")
    builder.button(text="🎁 ʀᴇꜰᴇʀ ʙᴏɴᴜꜱ", callback_data="admin_refer", style="primary")
    builder.button(text="💰 ᴜꜱᴇʀ ʙᴀʟᴀɴᴄᴇ", callback_data="admin_balance", style="primary")
    builder.button(text="📢 ʙʀᴏᴀᴅᴄᴀꜱᴛ", callback_data="admin_broadcast", style="primary")
    builder.button(text="💬 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}", style="primary")
    builder.button(text="🔙 ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu", style="danger")
    builder.adjust(1)
    return builder.as_markup()

def servers_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 ꜱᴇᴀʀᴄʜ ᴄᴏᴜɴᴛʀʏ", callback_data="search_country", style="primary")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu", style="danger")
    builder.adjust(1)
    return builder.as_markup()

# --- HANDLERS ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    await state.clear()

    if user_id == OWNER_ID:
        await send_main_menu(message, user_id)
        return

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].replace("ref_", ""))
        current_bonus = float(get_setting("refer_bonus"))
        if referrer_id != user_id:
            conn = sqlite3.connect("bot.db")
            cursor = conn.cursor()
            cursor.execute("SELECT refer_by FROM users WHERE user_id=?", (user_id,))
            existing_ref = cursor.fetchone()
            if existing_ref and existing_ref[0] is None:
                cursor.execute("UPDATE users SET refer_by=? WHERE user_id=?", (referrer_id, user_id))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (current_bonus, referrer_id))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (current_bonus, user_id))
                cursor.execute("INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)", (referrer_id, "CREDIT", current_bonus, "Referral Bonus"))
                cursor.execute("INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)", (user_id, "CREDIT", current_bonus, "Signup Referral Bonus"))
                conn.commit()
                try:
                    await bot.send_message(referrer_id, f"🎉 <b>Referral Bonus!</b>\n\nYou earned ₹{current_bonus} because someone joined using your link.", parse_mode="HTML")
                except:
                    pass
            conn.close()
    
    if user[2] == 0:
        await bot.send_message(OWNER_ID, f"🚨 <b>New User Alert!</b>\n\nName: {message.from_user.first_name}\nID: <code>{user_id}</code>", parse_mode="HTML")

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
        
        msg = await callback.message.answer("⏳ <i>Verifying your identity...</i>", parse_mode="HTML")
        await asyncio.sleep(1.5)
        await msg.edit_text("✅ <b>Verified successfully!</b>\n\n<i>Loading your store...</i>", parse_mode="HTML")
        await asyncio.sleep(1)
        await msg.delete()
        
        await send_main_menu(callback.message, callback.from_user.id)
    else:
        await callback.answer("❌ Wrong answer. Try again.", show_alert=True)

@dp.callback_query(F.data == "refer")
async def cb_refer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    current_bonus = float(get_setting("refer_bonus"))
    
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE refer_by=?", (user_id,))
    total_refs = cursor.fetchone()[0]
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu", style="danger")

    await callback.message.edit_text(
        f"<b>🎁 ʀᴇꜰᴇʀ & ᴇᴀʀɴ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>👥 <b>TOTAL REFERRALS :</b> {total_refs}\n"
        f"💵 <b>BONUS PER REFERRAL :</b> ₹{current_bonus:.2f}</blockquote>\n\n"
        f"Invite your friends using the link below. When they join, you and your friend both get ₹{current_bonus:.2f}!\n\n"
        f"🔗 <b>YOUR LINK :</b>\n<code>{ref_link}</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"<b>🛍 ꜱʜᴏᴘ — ꜱᴇᴀʀᴄʜ ꜱᴛᴏᴄᴋ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Click below to search accounts by country name (e.g. India, USA).</i>",
        reply_markup=servers_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "search_country")
async def cb_search_country(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"<b>🔍 ꜱᴇᴀʀᴄʜ ᴄᴏᴜɴᴛʀʏ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Type the country name you are looking for (e.g. India, USA):</i>",
        reply_markup=back_kb("buy"),
        parse_mode="HTML"
    )
    await state.set_state(SearchState.waiting_for_country)
    await callback.answer()

@dp.message(SearchState.waiting_for_country)
async def process_search_country(message: types.Message, state: FSMContext):
    query = message.text.strip().capitalize()
    
    # API se country code dhoondhna
    countries = await fetch_api_countries()
    target_country = next((c for c in countries if c['name'].lower() == query.lower()), None)
    
    if not target_country:
        await message.answer(f"❌ No country found with name '<b>{query}</b>'.", reply_markup=back_kb("buy"), parse_mode="HTML")
        await state.clear()
        return

    country_code = target_country['code']
    
    msg = await message.answer(f"⏳ <i>Fetching stock for {target_country['name']}...</i>", parse_mode="HTML")
    
    # API se stock fetch karna
    accounts = await fetch_api_accounts(country_code)
    
    if not accounts:
        await msg.edit_text(f"❌ <b>Out of stock!</b> No accounts available for {target_country['name']} right now.", reply_markup=back_kb("buy"), parse_mode="HTML")
        await state.clear()
        return

    # Database mein save karna (sirf pehla account dikhane ke liye)
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM api_stock WHERE country_code=?", (country_code,))
    
    count = 0
    for item in accounts:
        item_id = item['id']
        price = float(item['price'])
        cursor.execute("INSERT INTO api_stock (id, country_code, country_name, price) VALUES (?, ?, ?, ?)", (item_id, country_code, target_country['name'], price))
        count += 1
            
    conn.commit()
    conn.close()

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🛒 ᴠɪᴇᴡ ꜱᴛᴏᴄᴋ ({count} available)", callback_data=f"view_{country_code}", style="success")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="buy", style="danger")
    builder.adjust(1)

    await msg.edit_text(
        f"<b>📦 ꜱᴛᴏᴄᴋ — {target_country['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Total accounts found: {count}</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("view_"))
async def cb_view_stock(callback: types.CallbackQuery):
    country_code = callback.data.split("_", 1)[1]

    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, country_name, price FROM api_stock WHERE country_code=? LIMIT 1", (country_code,))
    item = cursor.fetchone()
    conn.close()

    if not item:
        await callback.answer("❌ Out of stock!", show_alert=True)
        return

    item_id, country_name, price = item

    builder = InlineKeyboardBuilder()
    builder.button(text=f"🛒 ʙᴜʏ ꜰᴏʀ ₹{price:.2f}", callback_data=f"api_buy_{item_id}_{price}", style="success")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="buy", style="danger")
    builder.adjust(1)

    await callback.message.edit_text(
        f"<b>📱 {country_name} ᴀᴄᴄᴏᴜɴᴛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Price: <b>₹{price:.2f}</b>\n\n"
        f"<i>Click below to purchase with wallet.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("api_buy_"))
async def cb_process_api_buy(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    item_id = parts[2]
    price = float(parts[3])
    user_id = callback.from_user.id
    user = get_user(user_id)
    balance = user[1]

    if balance < price:
        await callback.answer("❌ Insufficient balance! Please add funds.", show_alert=True)
        return

    await callback.message.edit_text("⏳ <i>Purchasing from API...</i>", parse_mode="HTML")
    
    api_order = await buy_api_account(item_id, price)
    
    if not api_order:
        await callback.message.edit_text("❌ <b>API Error:</b> Could not buy account. Please contact support.", reply_markup=back_kb(), parse_mode="HTML")
        return

    phone = api_order.get("phone", "Unknown")
    password = api_order.get("password")
    
    new_balance = balance - price
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
    cursor.execute("DELETE FROM api_stock WHERE id=?", (item_id,))
    cursor.execute("INSERT INTO orders (user_id, phone, price) VALUES (?, ?, ?)", (user_id, phone, price))
    cursor.execute("INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)", (user_id, "DEBIT", price, f"Bought {phone}"))
    conn.commit()
    conn.close()

    await bot.send_message(
        OWNER_ID,
        f"💰 <b>NEW SALE ALERT!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>👤 <b>User:</b> {callback.from_user.first_name} (@{callback.from_user.username})\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📱 <b>Account:</b> <code>{phone}</code>\n"
        f"💵 <b>Price:</b> ₹{price:.2f}</blockquote>",
        parse_mode="HTML"
    )

    text = f"<b>✅ ᴘᴜʀᴄʜᴀꜱᴇ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📱 <b>Phone:</b> <code>{phone}</code>\n"
    if password:
        text += f"🔑 <b>Password:</b> <code>{password}</code>\n"
    text += f"Price: <b>₹{price:.2f}</b>\n"
    text += f"Remaining Balance: <b>₹{new_balance:.2f}</b>\n\n"
    text += f"<i>Thank you for shopping with us!</i>"

    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "profile")
async def cb_profile(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    await callback.message.edit_text(
        f"<b>👤 ᴘʀᴏꜰɪʟᴇ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🆔 <b>USER ID :</b> <code>{callback.from_user.id}</code>\n"
        f"👤 <b>NAME :</b> {callback.from_user.first_name}\n"
        f"🔗 <b>USERNAME :</b> @{callback.from_user.username or 'None'}\n"
        f"💰 <b>BALANCE :</b> ₹{user[1]:.2f}</blockquote>\n\n"
        f"<i>Account details and current balance.</i>",
        reply_markup=back_kb(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data == "wallet")
async def cb_wallet(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ ᴀᴅᴅ ꜰᴜɴᴅꜱ", callback_data="add_funds", style="success")
    builder.button(text="📜 ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴꜱ", callback_data="transactions", style="primary")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu", style="danger")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"<b>💳 ᴡᴀʟʟᴇᴛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>💵 <b>BALANCE :</b> ₹{user[1]:.2f}\n"
        f"📥 <b>DEPOSITED :</b> ₹0.00\n"
        f"🛒 <b>SPENT :</b> ₹0.00</blockquote>\n\n"
        f"<i>Add funds to purchase accounts instantly.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

# --- ADD FUNDS LOGIC ---
@dp.callback_query(F.data == "add_funds")
async def cb_add_funds(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f"<b>💸 ᴀᴅᴅ ꜰᴜɴᴅꜱ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>💵 <b>MINIMUM :</b> ₹{MIN_DEPOSIT}\n"
        f"💳 <b>MAXIMUM :</b> ₹{MAX_DEPOSIT}</blockquote>\n\n"
        f"<i>Enter the amount you want to add to your wallet:</i>",
        reply_markup=back_kb("wallet"),
        parse_mode="HTML"
    )
    await state.set_state(WalletState.waiting_for_deposit_amount)
    await callback.answer()

@dp.message(WalletState.waiting_for_deposit_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < MIN_DEPOSIT or amount > MAX_DEPOSIT:
            await message.answer(f"❌ Amount must be between ₹{MIN_DEPOSIT} and ₹{MAX_DEPOSIT}.", reply_markup=back_kb("wallet"))
            return
    except ValueError:
        await message.answer("❌ Please enter a valid number.", reply_markup=back_kb("wallet"))
        return

    upi_link = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount:.2f}&cu=INR"
    
    await message.answer(
        f"<b>💳 ᴘᴀʏᴍᴇɴᴛ ᴅᴇᴛᴀɪʟꜱ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>💰 <b>Amount:</b> ₹{amount:.2f}\n"
        f"🏦 <b>UPI ID:</b> <code>{UPI_ID}</code></blockquote>\n\n"
        f"<i>1. Pay the amount using the UPI link below.</i>\n"
        f"<i>2. After payment, enter the 12-digit UTR/Transaction ID.</i>",
        parse_mode="HTML"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💸 ᴘᴀʏ ɴᴏᴡ", url=upi_link, style="success")
    await message.answer("👇 Click below to pay via any UPI app:", reply_markup=builder.as_markup())
    
    await message.answer(
        f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"   <b>Enter UTR / Transaction ID</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<i>Please enter your UTR number or Transaction ID from your UPI payment confirmation.</i>",
        parse_mode="HTML"
    )
    
    await state.update_data(deposit_amount=amount)
    await state.set_state(WalletState.waiting_for_utr)

@dp.message(WalletState.waiting_for_utr)
async def process_deposit_utr(message: types.Message, state: FSMContext):
    utr = message.text.strip()
    if len(utr) < 8:
        await message.answer("❌ Invalid UTR. Please check and send again.")
        return
        
    data = await state.get_data()
    amount = data.get("deposit_amount")
    user_id = message.from_user.id
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=f"approve_{user_id}_{amount}", style="success")
    builder.button(text="❌ Reject", callback_data=f"reject_{user_id}", style="danger")
    
    await bot.send_message(
        OWNER_ID,
        f"<b>💸 NEW DEPOSIT REQUEST</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>👤 <b>User:</b> {message.from_user.first_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"💰 <b>Amount:</b> ₹{amount}\n"
        f"🧾 <b>UTR:</b> <code>{utr}</code></blockquote>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    await message.answer(
        f"✅ <b>UTR Received!</b>\n\n"
        f"Admin will verify your payment shortly. Once approved, funds will be added to your wallet.",
        reply_markup=back_kb("main_menu"),
        parse_mode="HTML"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def cb_approve_funds(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    parts = callback.data.split("_")
    user_id = int(parts[1])
    amount = float(parts[2])
    
    conn = sqlite3.connect("bot.db")
    conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.execute("INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)", (user_id, "CREDIT", amount, "UPI Deposit"))
    conn.commit()
    conn.close()
    
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ <b>APPROVED</b>", reply_markup=None, parse_mode="HTML")
    await bot.send_message(user_id, f"✅ <b>₹{amount} has been added to your wallet!</b>\n\nThank you for the payment.", parse_mode="HTML")

@dp.callback_query(F.data.startswith("reject_"))
async def cb_reject_funds(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    user_id = int(callback.data.split("_")[1])
    
    await callback.message.edit_text(f"{callback.message.text}\n\n❌ <b>REJECTED</b>", reply_markup=None, parse_mode="HTML")
    await bot.send_message(user_id, "❌ <b>Payment Rejected.</b>\n\nPlease contact support if you think this is a mistake.", parse_mode="HTML")

@dp.callback_query(F.data == "transactions")
async def cb_transactions(callback: types.CallbackQuery):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT type, amount, note, date FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 5", (callback.from_user.id,))
    txns = cursor.fetchall()
    conn.close()

    if not txns:
        await callback.answer("No transactions found.", show_alert=True)
        return

    text = "<b>📜 RECENT TRANSACTIONS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for tx in txns:
        symbol = "🟢 +" if tx[0] == "CREDIT" else "🔴 -"
        text += f"{symbol}₹{tx[1]} | {tx[2]}\n"

    await callback.message.edit_text(text, reply_markup=back_kb("wallet"), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "support")
async def cb_support(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}", style="primary")
    builder.button(text="🔙 ʙᴀᴄᴋ", callback_data="main_menu", style="danger")
    builder.adjust(1)

    await callback.message.edit_text(
        f"<b>💬 ꜱᴜᴘᴘᴏʀᴛ ᴄᴇɴᴛᴇʀ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>🛠 <b>NEED HELP?</b>\n"
        f"Our support team is available 24/7 to assist you with any issues.</blockquote>\n\n"
        f"<i>Tap the button below to contact the admin directly.</i>",
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

@dp.callback_query(F.data == "orders")
async def cb_orders(callback: types.CallbackQuery):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT phone, price, date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (callback.from_user.id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await callback.answer("You haven't bought any accounts yet.", show_alert=True)
        return

    text = "<b>📦 YOUR RECENT ORDERS</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for o in orders:
        text += f"📱 <code>{o[0]}</code> | ₹{o[1]}\n<i>{o[2]}</i>\n\n"

    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer()

# --- ADMIN COMMANDS ---
@dp.message(Command("admin"))
async def admin_cmd(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    await message.answer(
        f"<b>⚙️ ᴏᴡɴᴇʀ ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 Welcome, <b>Owner</b>. Select an option below:\n",
        reply_markup=admin_menu_kb(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_sync_api")
async def cb_admin_sync_api(callback: types.CallbackQuery):
    if callback.from_user.id != OWNER_ID: return
    
    await callback.message.edit_text("⏳ <i>Syncing API connection...</i>", parse_mode="HTML")
    
    # Just checking if API is alive
    countries = await fetch_api_countries()
    
    if not countries:
        await callback.message.edit_text("❌ <b>API Error!</b> Could not connect to API.", reply_markup=back_kb("main_menu"), parse_mode="HTML")
        return

    await callback.message.edit_text(
        f"✅ <b>API Connected Successfully!</b>\n"
        f"Total Countries Available: {len(countries)}\n\n"
        f"<i>Note: Users can now search live stock directly from API.</i>", 
        reply_markup=back_kb("main_menu"), 
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_refer")
async def cb_admin_refer(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    current_bonus = get_setting("refer_bonus")
    await callback.message.edit_text(
        f"<b>🎁 REFERRAL MANAGER</b>\n\n"
        f"Current Bonus: <b>₹{current_bonus}</b>\n\n"
        f"<i>Send the new bonus amount (e.g. 10):</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_refer_bonus)
    await callback.answer()

@dp.message(AdminState.waiting_for_refer_bonus)
async def process_refer_bonus(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    try:
        new_bonus = float(message.text.strip())
        set_setting("refer_bonus", str(new_bonus))
        await message.answer(f"✅ <b>Referral bonus updated to ₹{new_bonus}</b>", parse_mode="HTML")
        await state.clear()
        await message.answer("⚙️ Admin Panel:", reply_markup=admin_menu_kb())
    except ValueError:
        await message.answer("❌ Please send a valid number.", parse_mode="HTML")

@dp.callback_query(F.data == "admin_channel")
async def cb_admin_channel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    current = get_setting("channel_id")
    await callback.message.edit_text(
        f"<b>📢 CHANNEL MANAGER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Current Channel: <code>{current}</code>\n\n"
        f"<i>Send the new channel username (e.g. @newchannel).</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_channel)
    await callback.answer()

@dp.message(AdminState.waiting_for_channel)
async def process_channel(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    new_channel = message.text.strip()
    if not new_channel.startswith("@"):
        new_channel = "@" + new_channel
    
    set_setting("channel_id", new_channel)
    await message.answer(f"✅ <b>Channel updated to {new_channel}</b>", parse_mode="HTML")
    await state.clear()
    await message.answer("⚙️ Admin Panel:", reply_markup=admin_menu_kb())

@dp.callback_query(F.data == "admin_balance")
async def cb_admin_balance(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await callback.message.edit_text(
        "<b>💰 USER BALANCE MANAGER</b>\n\n"
        "Format mein likh ke bhej:\n"
        "<code>UserID | Amount</code>\n"
        "<i>(Positive amount adds, negative deducts)</i>\n\n"
        "<b>Example:</b>\n"
        "<code>8468468528 | 500</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_user_balance)
    await callback.answer()

@dp.message(AdminState.waiting_for_user_balance)
async def process_user_balance(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    try:
        data = message.text.split("|")
        user_id = int(data[0].strip())
        amount = float(data[1].strip())

        conn = sqlite3.connect("bot.db")
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        conn.execute("INSERT INTO transactions (user_id, type, amount, note) VALUES (?, ?, ?, ?)", (user_id, "CREDIT" if amount > 0 else "DEBIT", abs(amount), "Admin Adjustment"))
        conn.commit()
        conn.close()

        await message.answer(f"✅ <b>Balance updated for user {user_id}.</b>", parse_mode="HTML")
        await bot.send_message(user_id, f"🔔 <b>Your wallet balance was updated by Admin by ₹{amount}</b>", parse_mode="HTML")
        await state.clear()
        await message.answer("⚙️ Admin Panel:", reply_markup=admin_menu_kb())
    except Exception:
        await message.answer("❌ Format galat hai. Wapas try kar:\n<code>8468468528 | 500</code>", parse_mode="HTML")

@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != OWNER_ID: return
    await callback.message.edit_text(
        "<b>📢 BROADCAST</b>\n\n"
        "<i>Send the message you want to broadcast to all users.</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminState.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != OWNER_ID: return
    
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    success = 0
    await message.answer(f"⏳ Broadcasting to {len(users)} users...")
    
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            success += 1
            await asyncio.sleep(0.05) 
        except Exception:
            pass

    await message.answer(f"✅ <b>Broadcast completed!</b>\nSent to {success} users.")
    await state.clear()
    await message.answer("⚙️ Admin Panel:", reply_markup=admin_menu_kb())

async def main():
    init_db()
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
