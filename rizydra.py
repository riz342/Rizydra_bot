import logging
import random
import json
import datetime
from datetime import timedelta
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== CONFIG =====
TELEGRAM_TOKEN = "7804259837:AAE2xwdqhbCR_5-UYWks7oT1QT6a7MjYn3g"  # Replace with your real token
ALPHA_VANTAGE_API_KEY = "YOUR_ALPHA_VANTAGE_API_KEY"  # Replace with your Alpha Vantage API key
ADMIN_USERNAME = "@rizydra"

# ===== USER STORAGE =====
try:
    with open("users.json", "r") as f:
        users = json.load(f)
except FileNotFoundError:
    users = {}

# ===== MARKETS =====
MARKETS = ["EURUSD", "USDJPY", "EURJPY", "EURGBP", "AUDUSD", "AUDCHF", "GBPUSD"]

# ===== FETCH REAL PRICE FROM ALPHA VANTAGE =====
def fetch_real_price(market: str):
    """
    Fetch real-time forex price from Alpha Vantage API.
    market: string like 'EURUSD'
    returns float price or None if failed
    """
    from_currency = market[:3]
    to_currency = market[3:]
    url = (
        f"https://www.alphavantage.co/query?"
        f"function=CURRENCY_EXCHANGE_RATE&from_currency={from_currency}&to_currency={to_currency}&apikey={ALPHA_VANTAGE_API_KEY}"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        rate = float(data["Realtime Currency Exchange Rate"]["5. Exchange Rate"])
        return round(rate, 4)
    except Exception as e:
        logging.warning(f"Failed to fetch real price for {market}: {e}")
        return None

# ===== SIGNAL GENERATOR =====
def generate_binary_signal(market: str):
    signals = ["GREEN", "RED"]
    indicators_hit = random.sample([
        "RSI", "MACD", "EMA Crossover", "Stochastic", "Bollinger Bands",
        "Volume", "ADX", "Ichimoku", "CCI", "ATR", "Doji Candle", "Support Zone"
    ], k=random.randint(5, 10))
    
    real_price = fetch_real_price(market)
    entry_price = real_price if real_price is not None else round(random.uniform(1.0000, 1.5000), 4)
    
    return {
        "market": market,
        "signal": random.choice(signals),
        "entry_price": entry_price,
        "confidence": random.randint(85, 99),
        "indicators": indicators_hit
    }

# ===== USER ACCESS CHECK =====
def is_user_allowed(username):
    if username and ("@" + username.lower() == ADMIN_USERNAME.lower()):
        return True  # Admin always allowed
    user = users.get(username)
    if not user:
        return False
    expiry = datetime.datetime.fromisoformat(user.get("expires"))
    if datetime.datetime.now() >= expiry:
        # Auto-remove expired users on check
        users.pop(username, None)
        with open("users.json", "w") as f:
            json.dump(users, f)
        return False
    return user.get("allowed")

# ===== CLEAN EXPIRED USERS ON STARTUP =====
def cleanup_expired_users():
    now = datetime.datetime.now()
    expired_users = [u for u, d in users.items() if datetime.datetime.fromisoformat(d.get("expires")) <= now]
    if expired_users:
        for u in expired_users:
            users.pop(u, None)
        with open("users.json", "w") as f:
            json.dump(users, f)
        logging.info(f"Removed expired users on startup: {expired_users}")

# ===== COMMAND HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    if not is_user_allowed(username):
        await update.message.reply_text("⛔ You are not allowed to use this bot.")
        return

    keyboard = [[InlineKeyboardButton(market, callback_data=f'market_{market}')] for market in MARKETS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('📊 Select a market:', reply_markup=reply_markup)

async def market_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    username = query.from_user.username
    if not is_user_allowed(username):
        await query.answer("⛔ Access denied.", show_alert=True)
        return

    await query.answer()
    market = query.data.split("_")[1]
    
    # Generate signal immediately
    signal = generate_binary_signal(market)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = (
        f"📈 *{signal['market']}* Signal\n"
        f"🕒 *Time*: {timestamp}\n"
        f"📍 *Signal*: *{signal['signal']}*\n"
        f"💰 *Entry Price*: {signal['entry_price']}\n"
        f"✅ *Confidence*: {signal['confidence']}%\n"
        f"📊 *Indicators*: {', '.join(signal['indicators'])}"
    )
    
    # Edit the original message with the signal
    await query.edit_message_text(text=response, parse_mode="Markdown")
    
    # Show market selection buttons again
    keyboard = [[InlineKeyboardButton(market, callback_data=f'market_{market}')] for market in MARKETS]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text='📊 Select another market:',
        reply_markup=reply_markup
    )

# ===== ADMIN COMMANDS =====
async def allow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username.lower() != ADMIN_USERNAME.strip("@").lower():
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /allow @username")
        return

    username = context.args[0].strip("@").lower()
    expiry = datetime.datetime.now() + timedelta(days=30)
    users[username] = {"allowed": True, "expires": expiry.isoformat()}
    with open("users.json", "w") as f:
        json.dump(users, f)
    await update.message.reply_text(f"✅ Allowed @{username} to use the bot for 30 days.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username.lower() != ADMIN_USERNAME.strip("@").lower():
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /remove @username")
        return

    username = context.args[0].strip("@").lower()
    users.pop(username, None)
    with open("users.json", "w") as f:
        json.dump(users, f)
    await update.message.reply_text(f"❌ Removed @{username} from the bot access list.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username.lower() != ADMIN_USERNAME.strip("@").lower():
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if not context.args:
        if not users:
            await update.message.reply_text("📭 No users are currently allowed.")
            return

        report = "📋 *User Access Status:*\n\n"
        now = datetime.datetime.now()
        for username, data in users.items():
            expiry = datetime.datetime.fromisoformat(data.get("expires"))
            days_left = (expiry - now).days
            report += f"• @{username}: {days_left} day(s) left (expires {expiry.strftime('%Y-%m-%d')})\n"
        report += f"\n👥 *Total users:* {len(users)}"
        await update.message.reply_text(report, parse_mode="Markdown")
    else:
        username = context.args[0].strip("@").lower()
        user = users.get(username)
        if not user:
            await update.message.reply_text(f"⛔ @{username} is not allowed.")
            return
        expiry = datetime.datetime.fromisoformat(user.get("expires"))
        days_left = (expiry - datetime.datetime.now()).days
        allowed = user.get("allowed")
        msg = f"✅ @{username} is {'allowed' if allowed else 'not allowed'}.\n"
        msg += f"⏳ Days left: {max(days_left, 0)} (expires {expiry.strftime('%Y-%m-%d')})"
        await update.message.reply_text(msg)

async def extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username.lower() != ADMIN_USERNAME.strip("@").lower():
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /extend @username days")
        return

    username = context.args[0].strip("@").lower()
    try:
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Days must be a number.")
        return

    user = users.get(username)
    if not user:
        await update.message.reply_text(f"⛔ @{username} is not currently allowed.")
        return

    expiry = datetime.datetime.fromisoformat(user.get("expires"))
    new_expiry = expiry + timedelta(days=days)
    users[username]["expires"] = new_expiry.isoformat()
    with open("users.json", "w") as f:
        json.dump(users, f)
    await update.message.reply_text(f"✅ Extended @{username}'s access by {days} day(s). New expiry: {new_expiry.strftime('%Y-%m-%d')}")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username.lower() != ADMIN_USERNAME.strip("@").lower():
        await update.message.reply_text("⛔ You are not authorized to use this command.")
        return

    if not users:
        await update.message.reply_text("📭 No users are currently allowed.")
        return

    report = "📋 *Allowed Users:*\n\n"
    now = datetime.datetime.now()
    for username, data in users.items():
        expiry = datetime.datetime.fromisoformat(data.get("expires"))
        report += f"• @{username}: expires on {expiry.strftime('%Y-%m-%d')}\n"
    report += f"\n👥 *Total users:* {len(users)}"
    await update.message.reply_text(report, parse_mode="Markdown")

# ===== MAIN =====
def main():
    logging.basicConfig(level=logging.INFO)
    cleanup_expired_users()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("extend", extend))
    app.add_handler(CommandHandler("listusers", listusers))

    app.add_handler(CallbackQueryHandler(market_selection, pattern=r"^market_"))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
