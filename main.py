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
# TELEGRAM
# =========================================================

telegram_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)
    .build()
)


# =========================================================
# FILA DOS LIVROS
# =========================================================
#
# Cada item representa:
#
# foto -> epub -> pdf -> figurinha
#
# A foto fica guardada até chegar o EPUB.
# =========================================================

book_queue = []


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
# LÊ PDF
# =========================================================

def extract_pdf_info(file_bytes):

    try:

        pdf = PdfReader(
            io.BytesIO(file_bytes)
        )

        title = None
        author = None

        if pdf.metadata:

            title = pdf.metadata.get("/Title")
            author = pdf.metadata.get("/Author")

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

        logger.exception(
            f"Erro lendo PDF: {e}"
        )

        return None, None


# =========================================================
# LÊ EPUB
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

        logger.exception(
            f"Erro lendo EPUB: {e}"
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
# ENVIA UM LIVRO COMPLETO
# =========================================================

async def send_complete_book(
    context,
    item
):

    title = item.get("title")
    author = item.get("author")

    caption = create_book_caption(
        title,
        author
    )

    # -----------------------------------------------------
    # 1. FOTO + LEGENDA
    # -----------------------------------------------------

    await context.bot.send_photo(
        chat_id=DESTINATION_CHAT_ID,
        photo=item["photo_file_id"],
        caption=caption
    )

    # -----------------------------------------------------
    # 2. EPUB SEM LEGENDA
    # -----------------------------------------------------

    await context.bot.send_document(
        chat_id=DESTINATION_CHAT_ID,
        document=item["epub_file_id"]
    )

    # -----------------------------------------------------
    # 3. PDF SEM LEGENDA
    # -----------------------------------------------------

    if item.get("pdf_file_id"):

        await context.bot.send_document(
            chat_id=DESTINATION_CHAT_ID,
            document=item["pdf_file_id"]
        )

    # -----------------------------------------------------
    # 4. FIGURINHA SEM LEGENDA
    # -----------------------------------------------------

    if item.get("sticker_file_id"):

        await context.bot.send_sticker(
            chat_id=DESTINATION_CHAT_ID,
            sticker=item["sticker_file_id"]
        )

    logger.info(
        f"Livro completo enviado: {title} - {author}"
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
        "📸 Foto adicionada à fila."
    )


# =========================================================
# EPUB / PDF
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

    # -----------------------------------------------------
    # IGNORA DOCUMENTOS QUE NÃO SÃO PDF/EPUB
    # -----------------------------------------------------

    if extension not in [
        "epub",
        "pdf"
    ]:

        logger.info(
            f"Documento ignorado: {filename}"
        )

        return

    # -----------------------------------------------------
    # PROCURA O PRIMEIRO LIVRO QUE AINDA PRECISA
    # DE EPUB/PDF
    # -----------------------------------------------------

    item = None

    for book in book_queue:

        if extension == "epub":
            if book["epub_file_id"] is None:
                item = book
                break

        elif extension == "pdf":
            if (
                book["epub_file_id"] is not None
                and book["pdf_file_id"] is None
            ):
                item = book
                break

    if item is None:

        logger.warning(
            f"{extension.upper()} recebido sem conjunto correspondente."
        )

        return

    # -----------------------------------------------------
    # EPUB
    # -----------------------------------------------------

    if extension == "epub":

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

        item["epub_file_id"] = (
            document.file_id
        )

        item["title"] = title
        item["author"] = author

        logger.info(
            f"📚 EPUB lido: {title} - {author}"
        )

    # -----------------------------------------------------
    # PDF
    # -----------------------------------------------------

    elif extension == "pdf":

        item["pdf_file_id"] = (
            document.file_id
        )

        logger.info(
            f"📕 PDF adicionado: {filename}"
        )

    # -----------------------------------------------------
    # NÃO ENVIA AINDA.
    #
    # Espera PDF + figurinha.
    # -----------------------------------------------------


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

    # -----------------------------------------------------
    # PROCURA O PRIMEIRO LIVRO QUE TEM EPUB + PDF
    # E AINDA NÃO TEM FIGURINHA
    # -----------------------------------------------------

    item = None

    for book in book_queue:

        if (
            book["epub_file_id"] is not None
            and book["pdf_file_id"] is not None
            and book["sticker_file_id"] is None
        ):

            item = book
            break

    if item is None:

        logger.warning(
            "Figurinha recebida sem livro completo."
        )

        return

    item["sticker_file_id"] = (
        message.sticker.file_id
    )

    logger.info(
        "🧚 Figurinha recebida."
    )

    # -----------------------------------------------------
    # AGORA O CONJUNTO ESTÁ COMPLETO
    # -----------------------------------------------------

    await send_complete_book(
        context,
        item
    )

    # Remove o livro da fila
    book_queue.remove(
        item
    )

    logger.info(
        "✅ Conjunto completo enviado para Tinker Books."
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
# PÁGINA PRINCIPAL
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


# =========================================================
# HEALTH
# =========================================================

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

        if not telegram_app._initialized:

            await telegram_app.initialize()

        await telegram_app.process_update(
            update
        )

        return "OK", 200

    except Exception:

        logger.exception(
            "Erro processando webhook"
        )

        return "ERROR", 500
