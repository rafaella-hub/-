import os
import io
import asyncio
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
# FILA DOS LIVROS
# =========================================================

book_queue = []


# =========================================================
# APLICAÇÃO TELEGRAM
# =========================================================

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)
    .build()
)


# =========================================================
# VERIFICA CANAL
# =========================================================

def is_from_source_channel(update):

    if not update.channel_post:
        return False

    return str(
        update.channel_post.chat_id
    ) == str(
        SOURCE_CHANNEL_ID
    )


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
            title_data[0][0].strip()
            if title_data
            and title_data[0][0]
            else None
        )

        author = (
            author_data[0][0].strip()
            if author_data
            and author_data[0][0]
            else None
        )

        return title, author

    except Exception as e:

        logger.exception(
            f"Erro lendo EPUB: {e}"
        )

        return None, None


# =========================================================
# EXTRAI INFORMAÇÕES DO PDF
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

        return title, author

    except Exception as e:

        logger.exception(
            f"Erro lendo PDF: {e}"
        )

        return None, None


# =========================================================
# LEGENDA DA FOTO
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
# ENVIA O CONJUNTO COMPLETO
# =========================================================

async def send_complete_book(
    context,
    book
):

    title = book["title"]
    author = book["author"]

    caption = create_book_caption(
        title,
        author
    )

    # -----------------------------------------------------
    # FOTO + LEGENDA
    # -----------------------------------------------------

    await context.bot.send_photo(
        chat_id=DESTINATION_CHAT_ID,
        photo=book["photo_file_id"],
        caption=caption
    )

    # -----------------------------------------------------
    # EPUB SEM LEGENDA
    # -----------------------------------------------------

    await context.bot.send_document(
        chat_id=DESTINATION_CHAT_ID,
        document=book["epub_file_id"]
    )

    # -----------------------------------------------------
    # PDF SEM LEGENDA
    # -----------------------------------------------------

    await context.bot.send_document(
        chat_id=DESTINATION_CHAT_ID,
        document=book["pdf_file_id"]
    )

    # -----------------------------------------------------
    # FIGURINHA SEM LEGENDA
    # -----------------------------------------------------

    await context.bot.send_sticker(
        chat_id=DESTINATION_CHAT_ID,
        sticker=book["sticker_file_id"]
    )

    logger.info(
        f"✅ CONJUNTO ENVIADO: {title} - {author}"
    )


# =========================================================
# FOTO
# =========================================================

async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_from_source_channel(update):
        return

    message = update.channel_post

    book_queue.append({

        "photo_file_id":
            message.photo[-1].file_id,

        "epub_file_id":
            None,

        "pdf_file_id":
            None,

        "sticker_file_id":
            None,

        "title":
            None,

        "author":
            None,
    })

    logger.info(
        "📸 FOTO adicionada à fila."
    )


# =========================================================
# DOCUMENTOS
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
        .rsplit(".", 1)[-1]
    )

    if extension not in [
        "epub",
        "pdf"
    ]:

        logger.info(
            f"Documento ignorado: {filename}"
        )

        return


    # =====================================================
    # EPUB
    # =====================================================

    if extension == "epub":

        # Procura o primeiro conjunto que ainda
        # não recebeu EPUB.

        book = None

        for item in book_queue:

            if (
                item["epub_file_id"]
                is None
            ):

                book = item
                break

        if book is None:

            logger.warning(
                "EPUB recebido sem foto correspondente."
            )

            return

        logger.info(
            f"📚 EPUB recebido: {filename}"
        )

        telegram_file = (
            await context.bot.get_file(
                document.file_id
            )
        )

        file_bytes = (
            await telegram_file.download_as_bytearray()
        )

        title, author = extract_epub_info(
            bytes(file_bytes)
        )

        book["epub_file_id"] = (
            document.file_id
        )

        book["title"] = title
        book["author"] = author

        logger.info(
            f"📖 EPUB identificado: "
            f"{title} - {author}"
        )

        return


    # =====================================================
    # PDF
    # =====================================================

    if extension == "pdf":

        # O PDF pertence ao primeiro conjunto
        # que já tem EPUB mas ainda não tem PDF.

        book = None

        for item in book_queue:

            if (
                item["epub_file_id"]
                is not None
                and item["pdf_file_id"]
                is None
            ):

                book = item
                break

        if book is None:

            logger.warning(
                "PDF recebido sem EPUB correspondente."
            )

            return

        book["pdf_file_id"] = (
            document.file_id
        )

        logger.info(
            f"📕 PDF recebido: {filename}"
        )


# =========================================================
# FIGURINHA
# =========================================================

async def handle_sticker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_from_source_channel(update):
        return

    message = update.channel_post

    # Procura o primeiro conjunto que tenha:
    #
    # FOTO + EPUB + PDF
    #
    # mas ainda não tenha figurinha.

    book = None

    for item in book_queue:

        if (
            item["epub_file_id"] is not None
            and item["pdf_file_id"] is not None
            and item["sticker_file_id"] is None
        ):

            book = item
            break

    if book is None:

        logger.warning(
            "Figurinha recebida sem conjunto completo."
        )

        return

    book["sticker_file_id"] = (
        message.sticker.file_id
    )

    logger.info(
        "🧚 FIGURINHA recebida."
    )

    # Agora o conjunto está completo.

    await send_complete_book(
        context,
        book
    )

    book_queue.remove(
        book
    )


# =========================================================
# HANDLERS
# =========================================================

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
        & filters.Document.ALL,
        handle_document
    )
)

telegram_app.add_handler(
    MessageHandler(
        filters.UpdateType.CHANNEL_POST
        & filters.Sticker.ALL,
        handle_sticker
    )
)


# =========================================================
# ROTAS
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return (
        "TinkerBooks Bot online!",
        200
    )


@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return "OK", 200


# =========================================================
# WEBHOOK
# =========================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
async def webhook():

    try:

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

        return "OK", 200

    except Exception as e:

        logger.exception(
            "Erro processando webhook"
        )

        return "ERROR", 500


# =========================================================
# INICIALIZAÇÃO
# =========================================================

async def initialize_bot():

    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN não configurado."
        )

    if not SOURCE_CHANNEL_ID:
        raise ValueError(
            "SOURCE_CHANNEL_ID não configurado."
        )

    if not DESTINATION_CHAT_ID:
        raise ValueError(
            "DESTINATION_CHAT_ID não configurado."
        )

    if not WEBHOOK_URL:
        raise ValueError(
            "WEBHOOK_URL não configurado."
        )

    await telegram_app.initialize()

    await telegram_app.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=False
    )

    logger.info(
        "🤖 TinkerBooks inicializado."
    )

    logger.info(
        f"Webhook: {WEBHOOK_URL}"
    )


# =========================================================
# IMPORTANTE
# =========================================================
#
# O Gunicorn carrega este arquivo.
# Não usamos asyncio.run() aqui.
#
# A inicialização será feita pelo hook do Flask.
# =========================================================

@app.before_request
async def ensure_telegram_initialized():

    if not telegram_app._initialized:

        await initialize_bot()
