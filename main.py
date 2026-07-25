import os
import io
import logging
import asyncio

from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

from pypdf import PdfReader
from ebooklib import epub


# =========================================================
# CONFIGURAÇÕES
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SOURCE_CHANNEL_ID = os.environ.get("SOURCE_CHANNEL_ID")
DESTINATION_CHAT_ID = os.environ.get("DESTINATION_CHAT_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")


# =========================================================
# LOG
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)


# =========================================================
# VERIFICA SE VEIO DO CANAL CERTO
# =========================================================

def is_from_source_channel(update):

    if not update.channel_post:
        return False

    chat_id = str(
        update.channel_post.chat_id
    )

    return chat_id == str(
        SOURCE_CHANNEL_ID
    )


# =========================================================
# EXTRAI TÍTULO E AUTOR DO PDF
# =========================================================

def extract_pdf_info(file_bytes):

    try:

        pdf = PdfReader(
            io.BytesIO(file_bytes)
        )

        title = None
        author = None

        if pdf.metadata:

            title = pdf.metadata.get(
                "/Title"
            )

            author = pdf.metadata.get(
                "/Author"
            )

        if not title or not author:

            text = ""

            for page in pdf.pages[:3]:

                try:
                    text += (
                        page.extract_text()
                        or ""
                    )
                except Exception:
                    pass

            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            if not title and lines:
                title = lines[0]

        return title, author

    except Exception as e:

        logger.error(
            f"Erro lendo PDF: {e}"
        )

        return None, None


# =========================================================
# EXTRAI TÍTULO E AUTOR DO EPUB
# =========================================================

def extract_epub_info(file_bytes):

    try:

        book = epub.read_epub(
            io.BytesIO(file_bytes)
        )

        title_data = book.get_metadata(
            "DC",
            "title"
        )

        author_data = book.get_metadata(
            "DC",
            "creator"
        )

        title = (
            title_data[0][0]
            if title_data
            else None
        )

        author = (
            author_data[0][0]
            if author_data
            else None
        )

        return title, author

    except Exception as e:

        logger.error(
            f"Erro lendo EPUB: {e}"
        )

        return None, None


# =========================================================
# LEGENDA DO LIVRO
# =========================================================

def create_book_caption(
    title,
    author
):

    title = (
        title
        or "Título não identificado"
    )

    author = (
        author
        or "Autor não identificado"
    )

    return (
        "➷ ✨ 💚 ✨ ➷\n\n"
        
        f"📖 {title}\n"
        
        f"❖ {author}\n\n"
        
        "🧚 TinkerBooks\n\n"
        "➷ ✨ 💚 ✨ ➷"
    )


# =========================================================
# PROCESSA FOTO
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_from_source_channel(update):
        return

    message = update.channel_post

    caption = message.caption or ""

    await context.bot.send_photo(
        chat_id=DESTINATION_CHAT_ID,
        photo=message.photo[-1].file_id,
        caption=caption
    )

    logger.info(
        "Foto enviada para Tinker Books."
    )


# =========================================================
# PROCESSA FIGURINHA
# =========================================================

async def handle_sticker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_from_source_channel(update):
        return

    message = update.channel_post

    await context.bot.send_sticker(
        chat_id=DESTINATION_CHAT_ID,
        sticker=message.sticker.file_id
    )

    logger.info(
        "Figurinha enviada para Tinker Books."
    )


# =========================================================
# PROCESSA PDF / EPUB
# =========================================================

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_from_source_channel(update):
        return

    message = update.channel_post

    if not message.document:
        return

    document = message.document

    filename = (
        document.file_name
        or ""
    )

    extension = (
        filename.lower()
        .split(".")[-1]
    )

    # Outros documentos são apenas encaminhados
    if extension not in [
        "pdf",
        "epub"
    ]:

        await context.bot.send_document(
            chat_id=DESTINATION_CHAT_ID,
            document=document.file_id
        )

        return

    logger.info(
        f"Livro recebido: {filename}"
    )

    telegram_file = (
        await context.bot.get_file(
            document.file_id
        )
    )

    file_bytes = (
        await telegram_file.download_as_bytearray()
    )

    title = None
    author = None

    if extension == "pdf":

        title, author = extract_pdf_info(
            bytes(file_bytes)
        )

    elif extension == "epub":

        title, author = extract_epub_info(
            bytes(file_bytes)
        )

    caption = create_book_caption(
        title,
        author
    )

    await context.bot.send_document(
        chat_id=DESTINATION_CHAT_ID,
        document=document.file_id,
        caption=caption
    )

    logger.info(
        f"Livro enviado: {title} - {author}"
    )


# =========================================================
# WEBHOOK
# =========================================================

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)
    .build()
)


telegram_app.add_handler(
    MessageHandler(
        filters.UpdateType.CHANNEL_POST
        & filters.PHOTO,
        handle_photo
    )
)


telegram_app.add_handler(
    MessageHandler(
        filters.UpdateType.CHANNEL_POST
        & filters.Sticker.ALL,
        handle_sticker
    )
)


telegram_app.add_handler(
    MessageHandler(
        filters.UpdateType.CHANNEL_POST
        & filters.Document.ALL,
        handle_document
    )
)


@app.route("/webhook", methods=["POST"])
async def webhook():

    try:

        data = request.get_json(
            force=True
        )

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        if not telegram_app.initialized:
            await telegram_app.initialize()

        await telegram_app.process_update(
            update
        )

        return "OK", 200

    except Exception as e:

        logger.exception(
            "Erro processando webhook"
        )

        return "ERROR", 500


# =========================================================
# INICIALIZAÇÃO
# =========================================================

async def setup_bot():

    await telegram_app.initialize()

    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=False
    )

    logger.info(
        f"Webhook configurado: {WEBHOOK_URL}"
    )


if __name__ == "__main__":

    asyncio.run(
        setup_bot()
    )

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
