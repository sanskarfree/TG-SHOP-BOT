import os
import sys
import subprocess
import asyncio
import logging
import sqlite3

# --- Auto Installer for Hosting Bot ---
def install_packages():
    try:
        import telegram
        import telethon
        import pytgcalls
    except ImportError:
        print("Installing required packages, please wait...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "python-telegram-bot", "telethon", "py-tgcalls"])
        print("Installation complete!")

install_packages()
# --------------------------------------

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8977568156:AAGxhU52C51b_FV96gtLUstwfEnq2eLBqwk")
API_ID = int(os.environ.get("API_ID", 39635732))
API_HASH = os.environ.get("API_HASH", "06ef6c0ec7f113707c9196af9712c43a")
OWNER_ID = int(os.environ.get("OWNER_ID", 8257117452))

DB_PATH = "/data/p2p_bot.db" if os.path.exists("/data") else "p2p_bot.db"
active_vc_clients = []

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session TEXT)''')
    conn.commit()
    conn.close()

init_db()
user_states = {}
login_clients = {}

def is_admin(user_id):
    if user_id == OWNER_ID: return True
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT phone, session FROM accounts")
    accounts = c.fetchall()
    conn.close()
    return accounts

def get_menu(user_id):
    is_owner = (user_id == OWNER_ID)
    
    keyboard = [
        [InlineKeyboardButton("📊 MY ACCOUNTS", callback_data='my_accounts')],
        [InlineKeyboardButton("🚀 JOIN CHANNEL", callback_data='join_channel')]
    ]
    
    if is_owner:
        keyboard.append([InlineKeyboardButton("📕 LEAVE CHANNEL", callback_data='leave_channel')])
        
    keyboard.extend([
        [InlineKeyboardButton("🫂 REACTION", callback_data='reaction')],
        [InlineKeyboardButton("🎙 VC JOIN", callback_data='vc_join'), InlineKeyboardButton("📕 VC LEAVE", callback_data='vc_leave')],
        [InlineKeyboardButton("🎂 BOT RESTART", callback_data='bot_restart')],
        [InlineKeyboardButton("➕ ADD ACCOUNT", callback_data='add_account')]
    ])
    
    if is_owner:
        keyboard.append([InlineKeyboardButton("➖ REMOVE ACCOUNT", callback_data='remove_account')])
        
    keyboard.append([InlineKeyboardButton("📋 ALL ADMIN LIST", callback_data='admin_list')])
    
    if is_owner:
        keyboard.append([InlineKeyboardButton("👑 ADD ADMIN", callback_data='add_admin'), InlineKeyboardButton("❌ REMOVE ADMIN", callback_data='remove_admin')])
        
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access Denied. You are not an admin.")
        return
    user_states.pop(user_id, None)
    await update.message.reply_text("👋 **Welcome!**\n\nSystem active hai. Niche menu se option chuniye:", reply_markup=get_menu(user_id), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("Access Denied", show_alert=True)
        return
    await query.answer()
    data = query.data
    
    is_owner = (user_id == OWNER_ID)
    owner_only = ['remove_account', 'leave_channel', 'add_admin', 'remove_admin']
    if not is_owner and data in owner_only:
        await query.answer("⚠️ Ye feature sirf Owner use kar sakta hai!", show_alert=True)
        return

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except:
        pass

    async def send_new_msg(text, reply_markup=None, parse_mode='Markdown'):
        if reply_markup is None:
            reply_markup = get_menu(user_id)
        await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)

    if data == 'my_accounts':
        accounts = get_all_sessions()
        if not accounts:
            await send_new_msg("❌ **Koi account add nahi hai.**")
            return
        text = f"📊 **Total Accounts Added:** {len(accounts)}\n\n"
        for idx, acc in enumerate(accounts, 1):
            text += f"{idx}. 📱 `{acc[0]}`\n"
        await send_new_msg(text)

    elif data == 'add_account':
        user_states[user_id] = 'waiting_for_phone'
        await send_new_msg("📱 **Add Account**\n\nKripya apna Phone Number bhejiyen (country code ke sath, jaise: `+919876543210`):")

    elif data == 'remove_account':
        accounts = get_all_sessions()
        if not accounts:
            await send_new_msg("❌ **Koi account add nahi hai.**")
            return
        text = "🗑 **Select account to remove:**\n\n"
        for acc in accounts:
            text += f"📱 {acc[0]}\n"
        user_states[user_id] = 'waiting_for_remove_phone'
        await send_new_msg(text + "\n\nPhone number type karke bhejo:")

    elif data == 'join_channel':
        user_states[user_id] = 'waiting_for_join_link'
        await send_new_msg("▶️ **Enter Channel Link:**\n\n• Public Link: `https://t.me/yourchannel` ya `@yourchannel`\n• Private Link: `https://t.me/+abcdef...`")

    elif data == 'leave_channel':
        user_states[user_id] = 'waiting_for_leave_link'
        await send_new_msg("📕 **Enter Channel Link to Leave:**\n\n• Public Link: `https://t.me/yourchannel` ya `@yourchannel`")

    elif data == 'vc_join':
        user_states[user_id] = 'waiting_for_vc_link'
        await send_new_msg("🎙 **Enter Group Link for VC:**\n\nLink bhejiyen jahan VC par accounts bhejna chahte hain:")

    elif data == 'vc_leave':
        if not active_vc_clients:
            await send_new_msg("⚠️ **Filhal koi bhi account VC par active nahi hai.**")
            return
        count = 0
        for client, pytgcalls in active_vc_clients:
            try:
                await pytgcalls.leave_group_call()
                await client.disconnect()
                count += 1
            except:
                pass
        active_vc_clients.clear()
        await send_new_msg(f"✅ **{count} accounts VC se leave ho gaye.**")

    elif data == 'bot_restart':
        await send_new_msg("🔄 **Bot Process Restarted!**\n\n✅ Aapke sabhi accounts safe hain. Naye orders start kar sakte hain.")

    elif data == 'admin_list':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        admins = c.fetchall()
        conn.close()
        text = f"👑 **Main Owner ID:** `{OWNER_ID}`\n\n👥 **Total Admins:** {len(admins)}\n\n📋 **Admin List:**\n"
        for i, admin in enumerate(admins, 1):
            text += f"{i}. `{admin[0]}`\n"
        await send_new_msg(text)

    elif data == 'add_admin':
        user_states[user_id] = 'waiting_for_add_admin'
        await send_new_msg("👑 **Send User ID to make Admin:**")
        
    elif data == 'remove_admin':
        user_states[user_id] = 'waiting_for_remove_admin'
        await send_new_msg("❌ **Send User ID to remove Admin:**")

    elif data == 'reaction':
        await send_new_msg("🫂 **Reaction feature coming soon!**")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    text = update.message.text.strip()

    if not state: return

    if state == 'waiting_for_phone':
        phone = text
        msg = await update.message.reply_text("⏳ Sending OTP...")
        try:
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            await client.send_code_request(phone)
            login_clients[user_id] = {"client": client, "phone": phone}
            user_states[user_id] = 'waiting_for_otp'
            await msg.edit_text("✅ **OTP sent!**\n\nPlease enter the OTP code (e.g., 12345):", parse_mode='Markdown')
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
            user_states.pop(user_id, None)

    elif state == 'waiting_for_otp':
        otp = text.replace(" ", "")
        msg = await update.message.reply_text("⏳ Verifying OTP...")
        data = login_clients.get(user_id)
        if not data:
            await msg.edit_text("❌ Session expired. Start again.")
            user_states.pop(user_id, None)
            return
        
        client = data["client"]
        phone = data["phone"]
        try:
            await client.sign_in(phone, otp)
            session_string = client.session.save()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO accounts (phone, session) VALUES (?, ?)", (phone, session_string))
            conn.commit()
            conn.close()
            
            await msg.delete()
            await update.message.reply_text("✅ **Account Added Successfully!**", reply_markup=get_menu(user_id), parse_mode='Markdown')
            
            await client.disconnect()
            user_states.pop(user_id, None)
            login_clients.pop(user_id, None)
            
        except SessionPasswordNeededError:
            user_states[user_id] = 'waiting_for_2fa'
            await msg.edit_text("🔐 **2-Step Verification is enabled.**\n\nPlease enter your password:")
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
            user_states.pop(user_id, None)

    elif state == 'waiting_for_2fa':
        password = text
        msg = await update.message.reply_text("⏳ Verifying Password...")
        data = login_clients.get(user_id)
        client = data["client"]
        phone = data["phone"]
        try:
            await client.sign_in(password=password)
            session_string = client.session.save()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO accounts (phone, session) VALUES (?, ?)", (phone, session_string))
            conn.commit()
            conn.close()
            
            await msg.delete()
            await update.message.reply_text("✅ **Account Added Successfully!**", reply_markup=get_menu(user_id), parse_mode='Markdown')
            
            await client.disconnect()
            user_states.pop(user_id, None)
            login_clients.pop(user_id, None)
        except Exception as e:
            await msg.edit_text(f"❌ Error: {str(e)}")
            user_states.pop(user_id, None)

    elif state == 'waiting_for_remove_phone':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM accounts WHERE phone = ?", (text,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Account `{text}` removed (if existed).", reply_markup=get_menu(user_id), parse_mode='Markdown')
        user_states.pop(user_id, None)

    elif state == 'waiting_for_join_link':
        user_states.pop(user_id, None)
        accounts = get_all_sessions()
        if not accounts:
            await update.message.reply_text("❌ No accounts found. Add accounts first.", reply_markup=get_menu(user_id))
            return
        
        msg = await update.message.reply_text(f"⏳ Joining {len(accounts)} accounts...\n\nProgress: 0/{len(accounts)}")
        success, failed = 0, 0
        
        clean_text = text.split('?')[0].strip()
        
        for idx, (phone, session) in enumerate(accounts, 1):
            try:
                client = TelegramClient(StringSession(session), API_ID, API_HASH)
                await client.connect()
                if "t.me/+" in clean_text or "t.me/joinchat/" in clean_text:
                    hash = clean_text.split('/')[-1].replace('+', '')
                    await client(ImportChatInviteRequest(hash))
                else:
                    username = clean_text.split('/')[-1].replace('@', '')
                    await client(JoinChannelRequest(username))
                success += 1
                await client.disconnect()
                await asyncio.sleep(2)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
                failed += 1
            except Exception:
                failed += 1
            
            if idx % 5 == 0:
                await msg.edit_text(f"⏳ Joining {len(accounts)} accounts...\n\nProgress: {idx}/{len(accounts)}")
                
        await msg.edit_text(f"✅ **Join Process Complete!**\n\nSuccess: {success}\nFailed: {failed}", reply_markup=get_menu(user_id), parse_mode='Markdown')

    elif state == 'waiting_for_leave_link':
        user_states.pop(user_id, None)
        accounts = get_all_sessions()
        if not accounts:
            await update.message.reply_text("❌ No accounts found.", reply_markup=get_menu(user_id))
            return
        
        msg = await update.message.reply_text(f"⏳ Leaving {len(accounts)} accounts...\n\nProgress: 0/{len(accounts)}")
        success, failed = 0, 0
        
        clean_text = text.split('?')[0].strip()
        
        for idx, (phone, session) in enumerate(accounts, 1):
            try:
                client = TelegramClient(StringSession(session), API_ID, API_HASH)
                await client.connect()
                username = clean_text.split('/')[-1].replace('@', '')
                await client(LeaveChannelRequest(username))
                success += 1
                await client.disconnect()
                await asyncio.sleep(2)
            except Exception:
                failed += 1
                
            if idx % 5 == 0:
                await msg.edit_text(f"⏳ Leaving {len(accounts)} accounts...\n\nProgress: {idx}/{len(accounts)}")
                
        await msg.edit_text(f"✅ **Leave Process Complete!**\n\nSuccess: {success}\nFailed: {failed}", reply_markup=get_menu(user_id), parse_mode='Markdown')

    elif state == 'waiting_for_vc_link':
        user_states.pop(user_id, None)
        accounts = get_all_sessions()
        if not accounts:
            await update.message.reply_text("❌ No accounts found.", reply_markup=get_menu(user_id))
            return
        
        msg = await update.message.reply_text(f"⏳ Connecting {len(accounts)} accounts to VC...\n\nProgress: 0/{len(accounts)}")
        success, failed = 0, 0
        
        clean_text = text.split('?')[0].strip()
        
        for idx, (phone, session) in enumerate(accounts, 1):
            try:
                client = TelegramClient(StringSession(session), API_ID, API_HASH)
                await client.connect()
                
                if "t.me/+" in clean_text or "t.me/joinchat/" in clean_text:
                    hash = clean_text.split('/')[-1].replace('+', '')
                    await client(ImportChatInviteRequest(hash))
                else:
                    username = clean_text.split('/')[-1].replace('@', '')
                    await client(JoinChannelRequest(username))
                
                entity = await client.get_entity(username if "t.me/+" not in clean_text else hash)
                
                pytgcalls = PyTgCalls(client)
                await pytgcalls.start()
                
                await pytgcalls.join_group_call(
                    entity.id,
                    MediaStream("https://github.com/anars/blank-audio/raw/master/1-second-of-silence.mp3")
                )
                
                active_vc_clients.append((client, pytgcalls))
                success += 1
                await asyncio.sleep(2)
            except Exception as e:
                print(f"VC Error: {e}")
                failed += 1
            
            if idx % 5 == 0:
                await msg.edit_text(f"⏳ Connecting {len(accounts)} accounts to VC...\n\nProgress: {idx}/{len(accounts)}")
                
        await msg.edit_text(f"✅ **VC Join Complete!**\n\nSuccess: {success}\nFailed: {failed}", reply_markup=get_menu(user_id), parse_mode='Markdown')

    elif state == 'waiting_for_add_admin':
        try:
            new_admin = int(text)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ Admin `{new_admin}` added.", reply_markup=get_menu(user_id), parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text("❌ Invalid ID.", reply_markup=get_menu(user_id))
        user_states.pop(user_id, None)

    elif state == 'waiting_for_remove_admin':
        try:
            rem_admin = int(text)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM admins WHERE user_id = ?", (rem_admin,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ Admin `{rem_admin}` removed.", reply_markup=get_menu(user_id), parse_mode='Markdown')
        except ValueError:
            await update.message.reply_text("❌ Invalid ID.", reply_markup=get_menu(user_id))
        user_states.pop(user_id, None)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Premium Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
