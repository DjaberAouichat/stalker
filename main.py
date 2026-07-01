import os
import requests
import sys
import time
import threading
import telebot
from telebot import types
from flask import Flask

# ==================== إعداد سيرفر ويب لمنصة Render ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>The IPTV Smart Guard Bot is Active 24/7</h1>", 200

def run_flask():
    # ريندر يمرر البورت تلقائياً عبر متغيرات البيئة، وإلا سيعمل على 8080 محلياً
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ==================== جلب الإعدادات بأمان من متغيرات البيئة ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PORTAL_URL = os.environ.get("PORTAL_URL", "http://dinodox.sbs/c/portal.php")
MAC_ADDRESS = os.environ.get("MAC_ADDRESS", "00:1A:79:33:29:6C")
TARGET_CHANNEL_ID = os.environ.get("TARGET_CHANNEL_ID", "1389618")
TARGET_CHANNEL_NAME = os.environ.get("TARGET_CHANNEL_NAME", "BEIN SPORTS MAX 1 AR SD")

headers = {
    "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
    "Cookie": f"mac={MAC_ADDRESS};"
}

# متغيرات التحكم بحالة الحارس
is_lock_active = True  
last_status = None     

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

def make_main_keyboard():
    """إنشاء أزرار تفاعلية تظهر أسفل شاشة التلغرام"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_start = types.KeyboardButton("▶️ تشغيل الحراسة")
    btn_stop = types.KeyboardButton("🛑 إيقاف الحراسة")
    btn_status = types.KeyboardButton("📊 فحص الحالة")
    markup.add(btn_start, btn_stop, btn_status)
    return markup

def send_telegram_alert(message):
    if bot and CHAT_ID:
        try:
            bot.send_message(CHAT_ID, message, parse_mode="Markdown", reply_markup=make_main_keyboard())
        except Exception as e:
            print(f"[-] فشل إرسال تلغرام: {e}")

def silent_lock_worker():
    """مسار حجز الخط المطور بتقنية التنقيط المستمر لمنع الـ Timeout"""
    global is_lock_active, last_status
    session = requests.Session()
    session.headers.update(headers)
    
    while True:
        if not is_lock_active:
            time.sleep(2)
            continue
            
        try:
            # 1. تنشيط الجلسة
            handshake_url = f"{PORTAL_URL}?type=stb&action=handshake"
            session.get(handshake_url, timeout=8)
            
            # 2. طلب رابط البث
            stream_cmd = f"{PORTAL_URL}?type=itv&action=create_link&cmd=ffmpeg+http://localhost/ch/{TARGET_CHANNEL_ID}"
            res_link = session.get(stream_cmd, timeout=8)
            stream_url = res_link.json().get("js", {}).get("cmd", "").replace("ffmpeg ", "")
            
            if not stream_url:
                time.sleep(2)
                continue
                
            # 3. فتح الاتصال والقراءة بالتنقيط الفائق لتوفير البيانات والـ IP
            with session.get(stream_url, stream=True, timeout=45) as stream_response:
                status = stream_response.status_code
                
                if status == 200:
                    if last_status != 200:
                        send_telegram_alert(f"🔒 *تم قفل الخط وطرد الطرف الآخر بنجاح!*\n📺 {TARGET_CHANNEL_NAME}\n🎯 الوضع: حراسة مستمرة سحابياً.")
                        last_status = 200
                    
                    start_time = time.time()
                    for chunk in stream_response.iter_content(chunk_size=256):
                        # دورة تجديد الاتصال كل 40 ثانية للأمان، أو عند الإيقاف
                        if not is_lock_active or (time.time() - start_time) > 40:
                            break
                        time.sleep(3) # تنقيط بطيء جداً (استهلاك معدوم للبيانات)
                else:
                    if last_status != status:
                        send_telegram_alert(f"⚠️ *تنبيه:* الخط مشغول بكود `{status}`.\nجاري إعادة الهجوم التلقائي...")
                        last_status = status
                    time.sleep(2)
                    
        except Exception as e:
            print(f"[-] خطأ في مسار الحجز: {e}")
            time.sleep(2)

# ==================== معالجة أزرار التلغرام ====================

if bot:
    @bot.message_handler(commands=['start', 'help'])
    def welcome_user(message):
        welcome_text = "🤖 *مرحباً بك في لوحة تحكم الحارس الذكي السحابية.*\n\nاستخدم الأزرار بالأسفل للتحكم التلقائي:"
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=make_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "▶️ تشغيل الحراسة")
    def start_lock_btn(message):
        global is_lock_active
        if not is_lock_active:
            is_lock_active = True
            bot.reply_to(message, "▶️ *تم تفعيل نظام الحراسة بالتنقيط الفائق المستمر.*", reply_markup=make_main_keyboard())
        else:
            bot.reply_to(message, "ℹ️ النظام نشط بالفعل ويقوم بعمله.", reply_markup=make_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "🛑 إيقاف الحراسة")
    def stop_lock_btn(message):
        global is_lock_active, last_status
        if is_lock_active:
            is_lock_active = False
            last_status = None
            bot.reply_to(message, "🛑 *تم سحب الحارس. الخط حر بالكامل الآن.*", reply_markup=make_main_keyboard())
        else:
            bot.reply_to(message, "ℹ️ النظام متوقف حالياً بالفعل.", reply_markup=make_main_keyboard())

    @bot.message_handler(func=lambda msg: msg.text == "📊 فحص الحالة")
    def status_btn(message):
        global is_lock_active, last_status
        state = "🟢 يحرس بنشاط (سحابي)" if is_lock_active else "🔴 متوقف ومتاح"
        last_code = last_status if last_status else "لا توجد استجابة بعد"
        
        status_text = (
            f"📊 *تقرير الحراسة السحابي:*\n\n"
            f"⚙️ وضع الحارس: {state}\n"
            f"📺 الهدف: {TARGET_CHANNEL_NAME}\n"
            f"💎 كود استجابة السيرفر: `{last_code}`"
        )
        bot.reply_to(message, status_text, parse_mode="Markdown", reply_markup=make_main_keyboard())

    @bot.message_handler(func=lambda msg: True)
    def handle_other_text(message):
        bot.send_message(message.chat.id, "🎛️ يرجى استخدام الأزرار المتاحة أسفل الشاشة:", reply_markup=make_main_keyboard())

# ==================== التشغيل الفعلي للمسارات ====================

if __name__ == "__main__":
    # 1. تشغيل سيرفر الويب لاستقبال إشارات ريندر وتفادي الـ Crash
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("[+] تم تشغيل سيرفر ويب Flask الوهمي...")
    
    # 2. إطلاق مسار حارس الـ IPTV في الخلفية
    lock_thread = threading.Thread(target=silent_lock_worker, daemon=True)
    lock_thread.start()
    print("[+] تم إطلاق مسار الحراسة الخلفي...")
    
    # 3. تشغيل البوت ليستقبل الأوامر في المسار الرئيسي
    if bot:
        print("[+] بوت التلغرام نشط ومستعد الآن...")
        send_telegram_alert("🚀 *تم إطلاق السكريبت على سيرفر Render وبدء الحراسة تلقائياً!*")
        try:
            bot.infinity_polling()
        except Exception as e:
            print(f"[-] خطأ في البوت: {e}")
            sys.exit(1)
    else:
        print("[!] خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة.")
        # نبقي السكريبت حياً لكي لا يسقط السيرفر بالكامل
        while True: time.sleep(10)
          
