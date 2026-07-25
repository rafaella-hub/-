import os
import io
import logging

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
# EXTRAI INFORMAÇÕES DO PDF
# =========================================================

def extract_pdf_info(file_bytes):

    try:
        pdf = PdfReader(io.BytesIO(file_bytes))

        title = None
        author = None

        if pdf.metadata:

            title = pdf.metadata.get("/Title")
            author = pdf.metadata.get("/Author")

        if not title or not author:

            text = ""

            for page in pdf.pages[:3]:

                try:
                    text += page.extract_text() or ""
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
# EXTRAI INFORMAÇÕES DO EPUB
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
# LEGENDA
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
# RECEBE FOTO
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    caption = message.caption or ""

    await message.copy(
        chat_id=DESTINATION_CHAT_ID,
        caption=caption
    )

    logger.info(
        "Foto enviada para o Tinker Books."
    )


# =========================================================
# RECEBE FIGURINHA
# =========================================================

async def handle_sticker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message:
        return

    await message.copy(
        chat_id=DESTINATION_CHAT_ID
    )

    logger.info(
        "Figurinha enviada para o Tinker Books."
    )


# =========================================================
# RECEBE PDF / EPUB
# =========================================================

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message or not message.document:
        return

    document = message.document

    filename = (
        document.file_name
        or ""
    )

    extension = (
        filename
        .lower()
        .split(".")[-1]
    )

    if extension not in [
        "pdf",
        "epub"
    ]:

        await message.copy(
            chat_id=DESTINATION_CHAT_ID
        )

        return

    logger.info(
        f"Recebendo livro: {filename}"
    )

    telegram_file = (
        await document.get_file()
    )

    file_bytes = (
        await telegram_file.download_as_bytearray()
    )

    title = None
    author = None

    if extension == "pdf":

        title, author = (
            extract_pdf_info(
                bytes(file_bytes)
            )
        )

    elif extension == "epub":

        title, author = (
            extract_epub_info(
                bytes(file_bytes)
            )
        )

    caption = create_book_caption(
        title,
        author
    )

    await message.copy(
        chat_id=DESTINATION_CHAT_ID,
        caption=caption
    )

    logger.info(
        f"Livro enviado: {title} - {author}"
    )


# =========================================================
# ERROS
# =========================================================

async def error_handler(
    update,
    context
):

    logger.error(
        "Erro no bot:",
        exc_info=context.error
    )


# =========================================================
# APLICAÇÃO TELEGRAM
# =========================================================

if not BOT_TOKEN:

    raise ValueError(
        "BOT_TOKEN não configurado."
    )

if not DESTINATION_CHAT_ID:

    raise ValueError(
        "DESTINATION_CHAT_ID não configurado."
    )


telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)
    .build()
)


telegram_app.add_handler(
    MessageHandler(
        filters.PHOTO,
        handle_photo
    )
)


telegram_app.add_handler(
    MessageHandler(
        filters.Sticker.ALL,
        handle_sticker
    )
)


telegram_app.add_handler(
    MessageHandler(
        filters.Document.ALL,
        handle_document
    )
)


telegram_app.add_error_handler(
    error_handler
)


# =========================================================
# WEBHOOK
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "TinkerBooks Bot online!"


@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return "OK"


@app.route(
    "/webhook",
    methods=["POST"]
)
async def webhook():

    data = request.get_json(
        force=True
    )

    update = Update.de_json(
        data,
        telegram_app.bot
    )

    await telegram_app.process_update(
        update
    )

    return "OK"


# =========================================================
# INICIALIZAÇÃO
# =========================================================

import asyncio


async def setup_bot():

    await telegram_app.initialize()

    if WEBHOOK_URL:

        await telegram_app.bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=False
        )

        logger.info(
            f"Webhook configurado: {WEBHOOK_URL}"
        )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    asyncio.run(setup_bot())

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
