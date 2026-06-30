import os
import re
import random
import asyncio
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"BOT TOKEN LOADED: {BOT_TOKEN[:10]}...")
REGISTER_URL = "https:/babehku9.xyz/register?voucher=1Ho3"

SUCCESS_TEXT = "Pendaftaran Berhasil"
DUPLICATE_PHONE_TEXT = "No. Handphone telah dipakai"

web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Bot Regis is running ✅"

def run_web():
    port = int(os.getenv("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

BANK_LIST = [
    "BCA", "MANDIRI", "BNI", "BRI", "CIMB NIAGA", "PERMATABANK",
    "DANAMON", "BANK LAIN", "BRI SYARIAH", "MANDIRI SYARIAH",
    "BSI", "QRIS", "SEABANK"
]

EWALLET_LIST = ["OVO", "GOPAY", "DANA", "LINKAJA", "SAKUKU"]
PULSA_LIST = ["TELKOMSEL", "XL AXIATA"]

def detect_rekening_type(bank_name):
    bank = bank_name.upper().strip()

    if bank in BANK_LIST:
        return "Bank"
    if bank in EWALLET_LIST:
        return "E-Wallet"
    if bank in PULSA_LIST:
        return "Pulsa"

    raise Exception(f"Provider tidak dikenal: {bank_name}")

async def add_rekening(page, data):
    jenis = detect_rekening_type(data["bank"])

    # tutup popup setelah register
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1000)

    # langsung masuk halaman deposit
    await page.goto(
        "https://babehku9.xyz/account/transaction?tab=deposit",
        timeout=60000
    )

    await page.wait_for_timeout(2000)

    # tutup popup lagi
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1000)

    # klik tambah rekening
    await page.get_by_text(
        "+ Tambah Rekening",
        exact=True
    ).click()

    await page.wait_for_timeout(1500)

    # pilih kategori
    await page.get_by_text(
        jenis,
        exact=True
    ).click()

    await page.wait_for_timeout(1000)

    # =========================
    # OPEN DROPDOWN BANK
    # =========================

    await page.get_by_text(
        "--Pilih--",
        exact=True
    ).click(force=True)
    
    await page.wait_for_timeout(1500)
    
    # =========================
    # PILIH PROVIDER
    # =========================
    
    provider = page.get_by_text(data["bank"], exact=False).last

    await provider.scroll_into_view_if_needed(timeout=10000)
    await page.wait_for_timeout(500)
    
    try:
        await provider.click(timeout=10000, force=True)
    except:
        print("ADDREK RETRY: provider outside viewport, JS click", flush=True)
        await provider.evaluate("(el) => el.click()")
        
    await page.wait_for_timeout(1000)

    # isi nomor rekening
    await page.get_by_placeholder(
        "Nomor akun Anda"
    ).fill(data["norek"])

    await page.wait_for_timeout(1000)

    # klik simpan
    await page.get_by_text(
        "Simpan",
        exact=True
    ).click()

    await page.wait_for_timeout(1500)

    # klik konfirmasi
    await page.get_by_text(
        "Konfirmasi",
        exact=True
    ).click()

    # tunggu notif rekening berhasil ditambah
    await page.get_by_text(
        "berhasil ditambah",
        exact=False
    ).wait_for(timeout=10000)
    
    return True

def generate_password():
    return f"babeh@{random.randint(100, 999)}"

def get_field(text, names):
    lines = text.splitlines()

    for line in lines:
        for name in names:
            pattern = rf"^\s*{re.escape(name)}\s*:\s*(.*)\s*$"
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group(1).strip()

    return ""

def parse_form(text):
    return {
        "nama": get_field(text, ["nama rek", "nama rekening", "nm rek", "nmrek", "nama"]),
        "email": get_field(text, ["email", "gmail", "mail"]),
        "phone": get_field(text, ["no whatsapp aktif", "nomor whatsapp", "no wa", "wa", "whatsapp", "nomor hp", "hp"]),
        "username": get_field(text, ["username", "user", "uid", "id", "request id", "id yang diinginkan"]),
        "password": get_field(text, ["password", "pass", "pw"]) or generate_password(),
        "norek": get_field(text, ["no rek", "nomor rekening", "no rekening", "nomer rekening", "nomor rek", "nomer rek", "rekening", "rek", "norek", "no akun", "nomor akun"]),
        "bank": get_field(text, ["bank", "rek bank", "jenis bank", "bank tujuan"]),
    }

async def close_popup(page):
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(200)
    return True

    close_selectors = [
        'button[aria-label="Close"]',
        'button[aria-label="close"]',
        '.modal button',
        '.modal [role="button"]',
        '[role="dialog"] button',
        'text=×',
        'text=✕',
        'text=X',
    ]

    for selector in close_selectors:
        try:
            elements = page.locator(selector)
            count = await elements.count()
            for i in range(count):
                try:
                    el = elements.nth(i)
                    if await el.is_visible(timeout=1000):
                        await el.click(force=True)
                        await page.wait_for_timeout(1000)
                        return True
                except Exception:
                    pass
        except Exception:
            pass

    await page.keyboard.press("Escape")
    await page.wait_for_timeout(1000)
    return False

async def register_member(data):
    print("REG STEP 1: mulai playwright", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()

        try:
            print("REG STEP 2: goto register", flush=True)
            await page.goto(REGISTER_URL, timeout=30000, wait_until="domcontentloaded")

            print("REG STEP 3: close popup", flush=True)
            await close_popup(page)
            await page.get_by_placeholder("Sesuai rekening bank Anda").wait_for(
                state="visible",
                timeout=20000
            )
            print("REG STEP 4: isi form", flush=True)
            await page.get_by_placeholder("Sesuai rekening bank Anda").fill(data["nama"], timeout=10000)
            
            await page.get_by_placeholder("Masukkan alamat email Anda").fill(data["email"], timeout=4000)
            
            await page.get_by_placeholder("Contoh: 8123456789").fill(data["phone"], timeout=4000)
            
            await page.get_by_placeholder("6-14 karakter huruf atau angka").fill(data["username"], timeout=4000)
            
            await page.get_by_placeholder("6-14 karakter huruf, angka, atau simbol").fill(data["password"], timeout=4000)
            
            await page.get_by_placeholder("Ulangi password di atas").fill(data["password"], timeout=4000)

            print("REG STEP 5: klik buat akun", flush=True)
            await page.get_by_text("Dengan login atau daftar").scroll_into_view_if_needed()
            await page.wait_for_timeout(500)

            # tutup popup/link WA kalau kebuka
            if "api.whatsapp.com" in page.url:
                await page.goto(REGISTER_URL, timeout=30000, wait_until="domcontentloaded")
                await close_popup(page)

            submit_btn = page.locator("form button").filter(has_text="Buat Akun").last
            await submit_btn.scroll_into_view_if_needed()
            await page.wait_for_timeout(800)
            # pastikan overlay WA/popup hilang dulu
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            
            await submit_btn.click(timeout=15000)

            print("REG STEP 6: cek hasil daftar", flush=True)
            try:
                await page.wait_for_function(
                    """() => document.body.innerText.includes('Pendaftaran Berhasil')
                    || document.body.innerText.includes('No. Handphone telah dipakai')
                    || !location.href.includes('register')""",
                    timeout=15000
                )
            except:
                pass
            
            page_text = await page.inner_text("body")

            if SUCCESS_TEXT in page_text:
                print("REG STEP 7: sukses daftar, tambah rekening", flush=True)
                await add_rekening(page, data)
                return "success", data["password"]

            if DUPLICATE_PHONE_TEXT in page_text:
                print("REG STEP 7: duplicate phone", flush=True)
                return "duplicate_phone", data["password"]

            if "babehku9.xyz/" in page.url and "register" not in page.url:
                print("REG STEP 7: url sudah keluar register, tambah rekening", flush=True)
                await add_rekening(page, data)
                return "success", data["password"]

            print("REG STEP 7: failed unknown", page.url, flush=True)
            return "failed", data["password"]

        except PlaywrightTimeoutError as e:
            print("REGISTER TIMEOUT ERROR:", e, flush=True)
            print("CURRENT URL:", page.url, flush=True)
            return "timeout", data.get("password", "")
        except Exception as e:
            print("REGISTER GENERAL ERROR:", repr(e), flush=True)
            print("CURRENT URL:", page.url, flush=True)
            raise
        finally:
            await browser.close()

def success_message(username, password):
    return f"""Akun 𝐁𝐀𝐁𝐄𝐇𝐖𝐈𝐍 sudah siap digunakan ya Kak, silahkan di coba untuk login. Terima kasih 😉

👉🏻 Username : {username}
👉🏻 Password : {password}
Jangan lupa ganti password setelah berhasil login !!

PENTING‼️
SELALU MENGGUNAKAN LINK DIBAWAH SAAT LOGIN ⬇️
🌐 cutt.ly/CuanBabehWin

🌐 Link Alternatif : 🔗 cutt.ly/BabehAlternatif
⚠️Info pola gacor klik 👉: cutt.ly/Contekan_Pola

Untuk mempermudah bermain silahkan download aplikasi kami
📲 Klik Apk Babehwin : cutt.ly/ApkBabehwin

WA Official 24 Jam : cutt.ly/Official_Babehwin"""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        print("HANDLE STEP 1: pesan diterima", flush=True)

        text = update.message.text or ""
        data = parse_form(text)

        required = ["nama", "email", "phone", "username", "norek", "bank"]
        missing = [key for key in required if not data[key]]

        if missing:
            await update.message.reply_text(
                "❌ Data belum lengkap bro.\n\nYang kurang: " + ", ".join(missing)
            )
            return

        await update.message.reply_text("⏳ Siap kak, data sedang didaftarkan...")
        print("HANDLE STEP 2: mulai register_member", flush=True)

        status, password = await asyncio.wait_for(register_member(data), timeout=120)
        print("HANDLE STEP 3: status =", status, flush=True)

        if status == "success":
            await update.message.reply_text(success_message(data["username"], password))
        elif status == "duplicate_phone":
            await update.message.reply_text(
                f"⚠️ Gagal daftar kak.\n\nNo whatsapp {data['phone']} sudah terdaftar."
            )
        else:
            await update.message.reply_text(
                f"❌ Gagal daftar kak.\n\nStatus: {status}"
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error proses:\n{type(e).__name__}: {e}")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN belum diset di Render Variables")

    Thread(target=run_web, daemon=True).start()
    import time
    time.sleep(2)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(
        poll_interval=0.5,
        timeout=30,
        read_timeout=60,
        write_timeout=60,
        connect_timeout=60,
        pool_timeout=60,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("ERROR START BOT:", flush=True)
        traceback.print_exc()
