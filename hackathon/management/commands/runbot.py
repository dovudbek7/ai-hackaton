
import os
import re
import logging
from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from hackathon.models import Application, BotUser, StudentTest

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States
(
    PHONE_INPUT,
    INTRIGUE_CHECK,
    CHANNEL_GATE,
    RESULT_DISPLAY
) = range(4)

# Required Channels
REQUIRED_CHANNELS = [
    "@robocode_andijan",
    "@andijan_it_community",
    "@tuaf_edu",
    "@aiHackaton"
]

@sync_to_async
def find_application(phone, user_id=None):
    clean_input = re.sub(r'\D', '', phone)
    if not clean_input:
        return None
        
    target_last_9 = clean_input[-9:]
    
    bot_user, _ = BotUser.objects.get_or_create(telegram_id=user_id)
    if bot_user.claimed_phone:
        db_phone_clean = re.sub(r'\D', '', bot_user.claimed_phone)
        if db_phone_clean.endswith(target_last_9):
            app = Application.objects.filter(phone__endswith=target_last_9).first()
            if app:
                test = app.student_tests.first()
                return {
                    'id': app.id,
                    'full_name': app.full_name,
                    'status': app.status,
                    'umumiy_holat': app.overall_status,
                    'test_ai_holat': test.ai_holat if test else StudentTest.AI_HOLAT_KUTILAYAPTI,
                    'already_claimed': True
                }
        else:
            return {'error': 'limit_reached'}

    candidates = Application.objects.all()
    
    for app in candidates:
        if not app.phone:
            continue
        db_phone_clean = re.sub(r'\D', '', app.phone)
        if db_phone_clean.endswith(target_last_9):
            test = app.student_tests.first()
            return {
                'id': app.id,
                'full_name': app.full_name,
                'status': app.status,
                'umumiy_holat': app.overall_status,
                'test_ai_holat': test.ai_holat if test else StudentTest.AI_HOLAT_KUTILAYAPTI,
            }
            
    return None

@sync_to_async
def claim_application(phone, user_id, username=None):
    clean_phone = re.sub(r'\D', '', phone)
    bot_user, _ = BotUser.objects.get_or_create(telegram_id=user_id)
    if not bot_user.claimed_phone:
        bot_user.claimed_phone = clean_phone
        if username and not bot_user.username:
            bot_user.username = username
        bot_user.save()


class Command(BaseCommand):
    help = "Run Telegram bot"

    def handle(self, *args, **kwargs):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not found."))
            return

        application = ApplicationBuilder().token(token).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                PHONE_INPUT: [
                    CallbackQueryHandler(self.ask_phone_handler, pattern="^start_check$"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_phone)
                ],
                INTRIGUE_CHECK: [
                    CallbackQueryHandler(self.proceed_to_channel_gate, pattern="^see_result$"),
                    CallbackQueryHandler(self.retry_check, pattern="^retry_check$")
                ],
                CHANNEL_GATE: [
                    CallbackQueryHandler(self.verify_channels, pattern="^check_subs$")
                ],
                RESULT_DISPLAY: [
                    CallbackQueryHandler(self.restart_flow, pattern="^restart_flow$")
                ]
            },
            fallbacks=[CommandHandler("start", self.start)],
            per_message=False
        )

        application.add_handler(conv_handler)
        application.add_error_handler(self.handle_error)
        
        self.stdout.write(self.style.SUCCESS("Bot started polling..."))
        application.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        info_text = (
            "🤖 **Assalomu alaykum!**\n\n"
            "Ushbu bot orqali siz hakatonda qatnashish uchun topshirgan "
            "arizangiz holatini tekshirishingiz mumkin.\n\n"
            "📋 **Eslatma:**\n"
            "• Natijalar maxfiy va faqat shaxsiy tekshirish uchun.\n"
            "• Bitta qatnashuvchi faqat o'zini natijasini ko'rishi mumkin.\n"
            "• Agar ma'lumot topilmasa, qayta urinib ko'rishingiz mumkin."
        )
        
        keyboard = [[InlineKeyboardButton("🚀 Tekshirish", callback_data="start_check")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(info_text, parse_mode='Markdown', reply_markup=reply_markup)
        return PHONE_INPUT

    # PHONE INPUT FIRST
    async def ask_phone_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "Telefon raqamingizni kiriting:\n"
            "(Masalan: 991234567 yoki +998991234567)"
        )
        return PHONE_INPUT
    
    async def verify_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        missing_channels = []
        
        for channel in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
                if member.status in ['left', 'kicked', 'restricted']:
                    missing_channels.append(channel)
            except Exception as e:
                logger.warning(f"Failed channel check {channel}: {e}")
                # If we can't verify, assume user is NOT subscribed
                # This ensures users must still subscribe even if bot lacks permissions
                missing_channels.append(channel)

        if missing_channels:
            keyboard = []
            for channel in missing_channels:
                url = f"https://t.me/{channel.replace('@', '')}"
                keyboard.append([InlineKeyboardButton(f"Obuna bo'lish {channel}", url=url)])
            
            keyboard.append([InlineKeyboardButton("Tekshirish", callback_data="check_subs")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = "Natijani ko'rish uchun quyidagi kanallarga obuna bo'ling \n (Endi xizmatchilikda nima deysiz 😉)"
            
            if update.callback_query:
                try:
                    await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
                except Exception as e:
                     if "not modified" in str(e):
                        await update.callback_query.answer("O'zi atiga to'rt dona kanal sizga og'irlik qilmasa kerak Djigar 😆", show_alert=True)
            else:
                 await update.message.reply_text(msg, reply_markup=reply_markup)
            
            return CHANNEL_GATE
        else:
            return await self.show_result(update, context)

    # PHONE INPUT
    async def process_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        phone = re.sub(r'\D', '', text)
        
        if len(phone) < 9:
            await update.message.reply_text("Telefon raqam noto'g'ri. Qaytadan kiriting (kamida 9 ta raqam):")
            return PHONE_INPUT
        
        context.user_data['phone'] = phone
        
        app_data = await find_application(phone, user_id=update.effective_user.id)
        
        if isinstance(app_data, dict) and app_data.get('error') == 'limit_reached':
             await update.message.reply_text(
                "❌ **Siz allaqachon birinchi arizangizni tekshirgansiz.**\n\n"
                "Bitta Telegram akkauntdan faqat bitta arizani ko'rish mumkin.",
                parse_mode='Markdown'
            )
             return PHONE_INPUT

        if not app_data:
            keyboard = [[InlineKeyboardButton("Qayta tekshirish", callback_data="retry_check")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Bu ma'lumotlar bo'yicha ro'yxatdan o'tish topilmadi",
                reply_markup=reply_markup
            )
            return INTRIGUE_CHECK
        
        context.user_data['app_data'] = app_data
        
        full_name = app_data['full_name']
        
        msg = (
            f"Biz **{full_name}** uchun natijani topdik 🎉 \n"
            "👀 Natijani ko'rishga tayyormisiz? "
        )
        
        keyboard = [[InlineKeyboardButton("Ha, natijani ko'rish 🎉", callback_data="see_result")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)
        return INTRIGUE_CHECK

    async def retry_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "Telefon raqamingizni kiriting:\n"
            "(Masalan: 991234567 yoki +998991234567)"
        )
        return PHONE_INPUT

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")
        if "Conflict" in str(context.error):
            logger.error("Multiple bot instances detected. Please stop other instances.")
        elif "Timed out" in str(context.error):
            logger.warning("Network timeout. Retrying...")
            
    # RE-VERIFY CHANNELS BEFORE RESULT
    async def proceed_to_channel_gate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        return await self.verify_channels_for_result(update, context)

    async def verify_channels_for_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        missing_channels = []
        
        for channel in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
                if member.status in ['left', 'kicked', 'restricted']:
                    missing_channels.append(channel)
            except Exception as e:
                logger.warning(f"Failed channel check {channel}: {e}")
                # If we can't verify, assume user is NOT subscribed
                missing_channels.append(channel)

        if missing_channels:
            keyboard = []
            for channel in missing_channels:
                url = f"https://t.me/{channel.replace('@', '')}"
                keyboard.append([InlineKeyboardButton(f"Obuna bo'lish {channel}", url=url)])
            
            keyboard.append([InlineKeyboardButton("Tekshirish", callback_data="check_subs")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            msg = "Natijani ko'rish uchun quyidagi kanallarga obuna bo'ling \n (Endi xizmatchilikda nima deysiz 😉)"
            
            try:
                await update.callback_query.edit_message_text(msg, reply_markup=reply_markup)
            except Exception as e:
                 if "not modified" in str(e):
                    await update.callback_query.answer("O'zi to'rt donagina kanal, sizga og'irlik qilmasa kerak Djigar 😆", show_alert=True)
            
            return CHANNEL_GATE
        else:
            return await self.show_result(update, context)

    # RESULT DISPLAY
    async def show_result(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        app_data = context.user_data.get('app_data')
        if not app_data:
            return await self.start(update, context)
            
        username = update.effective_user.username or update.effective_user.first_name or None
        await claim_application(context.user_data.get('phone'), update.effective_user.id, username)
            
        umumiy_holat = app_data.get('umumiy_holat') or Application.OVERALL_STATUS_KUTILAYAPTI
        test_ai_holat = app_data.get('test_ai_holat') or StudentTest.AI_HOLAT_KUTILAYAPTI
        
        response = ""
        if umumiy_holat == Application.OVERALL_STATUS_QABUL_QILINDI:
            response = "✅ *Tabriklaymiz!*\nArizangiz QABUL QILINDI!\n\n"
            response += "📝 *Test javoblari:*\n"
            if test_ai_holat == StudentTest.AI_HOLAT_QABUL_QILINDI:
                response += "• O‘tdingiz\n\n"
            elif test_ai_holat == StudentTest.AI_HOLAT_QABUL_QILINMADI:
                response += "• O‘tmadingiz\n\n"
            else:
                response += "• Natija kutilmoqda\n\n"
        elif umumiy_holat == Application.OVERALL_STATUS_QABUL_QILINMADI:
            response = "❌ *Afsuski,* arizangiz RAD ETILDI.\n\n"
        else:
            response = "⏳ *Arizangiz ko'rib chiqilmoqda...*\n\n"
        
        response += f"👤 *Ism:* {app_data['full_name']}\n"
        # response += f"📋 *Holat:* {status}\n"
        
        # keyboard = [[InlineKeyboardButton("♻️ Boshidan", callback_data="restart_flow")]]
        # reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.effective_message.reply_text(
            response,
            parse_mode='Markdown'
        )
        return RESULT_DISPLAY

    async def restart_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        context.user_data.pop('phone', None)
        context.user_data.pop('app_data', None)
        
        await query.edit_message_text(
            "Telefon raqamingizni kiriting:\n"
            "(Masalan: 991234567 yoki +998991234567)"
        )
        return PHONE_INPUT
