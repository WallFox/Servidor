import os
import json
import logging
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters
)
from mqtt_handler import MQTTClientHandler

load_dotenv()

# --- CONFIGURACIÓN ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_PARAMS = {
    "host": os.getenv("PG_HOST"),
    "port": os.getenv("PG_PORT"),
    "dbname": os.getenv("PG_DB"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASS")
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

mqtt_client = MQTTClientHandler()
mqtt_client.start()


# --- DATABASE ---
def get_conn():
    return psycopg2.connect(**DB_PARAMS)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username    TEXT,
                    registered_at TIMESTAMP,
                    active      BOOLEAN DEFAULT TRUE
                );
            """)
            conn.commit()


def add_user(tg_id, username):
    now = datetime.utcnow()
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Verificar si ya existe
            cur.execute("SELECT active FROM users WHERE telegram_id = %s;", (tg_id,))
            row = cur.fetchone()

            if row is not None:
                if not row[0]:
                    # Usuario ya registrado pero inactivo (baneado)
                    return False
                else:
                    # Ya está registrado y activo, solo actualiza nombre
                    cur.execute("""
                        UPDATE users SET username = %s WHERE telegram_id = %s;
                    """, (username, tg_id))
                    conn.commit()
                    return True

            # Nuevo usuario, insertar
            cur.execute("""
                INSERT INTO users (telegram_id, username, registered_at, active)
                VALUES (%s, %s, %s, TRUE);
            """, (tg_id, username, now))
            conn.commit()
            return True


def deactivate_user(tg_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = FALSE WHERE telegram_id = %s;", (tg_id,))
            conn.commit()


def activate_user(tg_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = TRUE WHERE telegram_id = %s;", (tg_id,))
            conn.commit()


def list_all_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT telegram_id, username, registered_at, active FROM users ORDER BY registered_at;")
            return cur.fetchall()


def is_active_user(tg_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT active FROM users WHERE telegram_id = %s;", (tg_id,))
            row = cur.fetchone()
            return bool(row and row[0])


# --- MENÚ BOTONES ---
def crear_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Ver datos", callback_data="ver_datos")],
        [
            InlineKeyboardButton("💡 On LED Sensor", callback_data="led_sensor_on"),
            InlineKeyboardButton("💡 On LED Status", callback_data="led_status_on")
        ],
        [
            InlineKeyboardButton("❌ Off LED Sensor", callback_data="led_sensor_off"),
            InlineKeyboardButton("❌ Off LED Status", callback_data="led_status_off")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Para usar este servicio,\nenvía /register"
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.full_name

    result = add_user(tg_id, username)

    if result is False:
        await update.message.reply_text("⛔ Has sido desactivado por un administrador. Contacta con soporte.")
        return

    await update.message.reply_text("✅ Te has registrado con éxito. ¡Bienvenido!")
    await update.message.reply_text("🦊 ¿Qué deseas hacer?", reply_markup=crear_menu())


async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    deactivate_user(tg_id)
    await update.message.reply_text("❌ Te has dado de baja. Ya no podrás usar los comandos.")


async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    rows = list_all_users()
    text = "📋 Usuarios registrados:\n"
    for uid, usr, ts, active in rows:
        status = "✔️ Activo" if active else "⛔ Inactivo"
        text += f"- {usr} (ID:{uid}) — {status} — registrado {ts:%Y-%m-%d %H:%M}\n"
    await update.message.reply_text(text)


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ No estás autorizado para usar este comando.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❗ Usa el comando así: /ban <telegram_id>")
        return

    target_id = int(context.args[0])
    deactivate_user(target_id)
    await update.message.reply_text(f"🚫 Usuario {target_id} dado de baja.")


async def activar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ No estás autorizado para usar este comando.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❗ Usa el comando así: /activar <telegram_id>")
        return

    target_id = int(context.args[0])
    activate_user(target_id)
    await update.message.reply_text(f"✅ Usuario {target_id} ha sido reactivado.")


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id

    if not is_active_user(tg_id):
        await update.message.reply_text("⛔ Debes registrarte primero con /register.")
        return

    await update.message.reply_text("📲 ¿Qué deseas hacer?", reply_markup=crear_menu())


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    if not is_active_user(tg_id):
        await query.edit_message_text("⛔ No estás autorizado. Usa /register primero.")
        return

    if query.data == "ver_datos":
        data = mqtt_client.get_last_message()
        if not data:
            await query.answer("Esperando datos del ESP...⏳", show_alert=True)
            return
        try:
            json_data = json.loads(data)

            # ── FILTRAR SOLO DATOS DEL SENSOR ──
            if json_data.get("id") != "Sensor_ESP":
                await query.answer("No hay datos de sensor disponibles", show_alert=True)
                return

            # ── Si llegamos aquí, sí es un mensaje de Sensor_ESP ──
            estado = "🟢 ON" if json_data["dato_button"] else "🔴 OFF"
            texto = (
                f"📡 ID: {json_data['id']}\n"
                f"🌡️ Temp: {json_data['dato_temp']} °C\n"
                f"💧 Humedad: {json_data['dato_hum']} %\n"
                f"🔘 Botón: {estado}"
            )
            await query.message.reply_text(texto)

        except json.JSONDecodeError:
            await query.message.reply_text("⚠️ Error: JSON inválido.")
        except KeyError as e:
            await query.message.reply_text(f"⚠️ Falta la clave {e} en los datos.")
        except Exception as e:
            await query.message.reply_text(f"Error leyendo datos: {e}")


    # ── BOTONES LEDs ──
    elif query.data == "led_sensor_on":
        msg = {"id": "Telegram", "dato_button": 1}
        mqtt_client.publish(json.dumps(msg), topic="Fox_32_Home/Status")
        await query.answer("Led Sensor 🟢 ON")


    elif query.data == "led_sensor_off":
        msg = {"id": "Telegram", "dato_button": 0}
        mqtt_client.publish(json.dumps(msg), topic="Fox_32_Home/Status")
        await query.answer("Led Sensor 🔴 OFF")


    elif query.data == "led_status_on":
        msg = {"id": "Telegram", "dato_button": 1}
        mqtt_client.publish(json.dumps(msg), topic="Fox_32_Home/Sensor")
        await query.answer("Led Status 🟢 ON")


    elif query.data == "led_status_off":
        msg = {"id": "Telegram", "dato_button": 0}
        mqtt_client.publish(json.dumps(msg), topic="Fox_32_Home/Sensor")
        await query.answer("Led Status 🔴 OFF")


async def texto_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not is_active_user(tg_id):
        return
    await update.message.reply_text(f"Recibí tu mensaje: {update.message.text}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = update.effective_user.id == ADMIN_ID

    text = "📖 *Comandos disponibles:*\n"
    text += "/register — Registrarte en el sistema\n"
    text += "/unregister — Darse de baja del bot\n"
    text += "/help — Mostrar esta ayuda\n"

    if is_admin:
        text += "\n🔧 *Comandos de administrador:*\n"
        text += "/listusers — Ver usuarios registrados\n"
        text += "/ban <id> — Desactivar usuario\n"
        text += "/activar <id> — Reactivar usuario\n"
        text += "Eres el mejor sigue adelante 🦊\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# --- MAIN ---
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("unregister", unregister))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("activar", activar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texto_general))
    app.add_handler(CallbackQueryHandler(callback_handler))

    app.run_polling()
