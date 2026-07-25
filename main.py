import os
import io
import re
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

from pypdf import PdfReader
from ebooklib import epub
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURAÇÕES
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DESTINATION_CHAT_ID = os.environ.get("DESTINATION_CHAT_ID")


# =========================================================
# LOG
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# EXTRAI TÍTULO E AUTOR DO PDF
# =========================================================

def extract_pdf_info(file_bytes):

    try:
        pdf = PdfReader(io.BytesIO(file_bytes))

        metadata = pdf.metadata

        title = None
        author = None

        if metadata:
            title = metadata.get("/Title")
            author = metadata.get("/Author")

        # Se não encontrar nos metadados,
        # tenta procurar no início do texto
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

        title = clean_text(title)
        author = clean_text(author)

        return title, author

    except Exception as e:
        logger.error(f"Erro lendo PDF: {e}")
        return None, None


# =========================================================
# EXTRAI TÍTULO E AUTOR DO EPUB
# =========================================================

def extract_epub_info(file_bytes):

    try:

        book = epub.read_epub(
            io.BytesIO(file_bytes)
        )

        title = book.get_metadata(
            "DC",
            "title"
        )

        author = book.get_metadata(
            "DC",
            "creator"
        )

        title = title[0][0] if title else None
        author = author[0][0] if author else None

        return clean_text(title), clean_text(author)

    except Exception as e:
        logger.error(f"Erro lendo EPUB: {e}")
        return None, None


# =========================================================
# LIMPA TEXTO
# =========================================================

def clean_text(text):

    if not text:
        return None

    text = str(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# =========================================================
# MONTA LEGENDA DO LIVRO
# =========================================================

def create_book_caption(
    title,
    author,
    original_caption=None
):

    title = title or "Título não identificado"
    author = author or "Autor não identificado"

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

    logger.info("Foto enviada para o grupo.")


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

    logger.info("Figurinha enviada para o grupo.")


# =========================================================
# RECEBE DOCUMENTOS PDF / EPUB
# =========================================================

async def handle_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message

    if not message or not message.document:
        return

    document = message.document

    filename = document.file_name or ""

    extension = filename.lower().split(".")[-1]

    if extension not in ["pdf", "epub"]:

        await message.copy(
            chat_id=DESTINATION_CHAT_ID
        )

        return

    logger.info(
        f"Recebendo livro: {filename}"
    )

    # Baixa o arquivo do Telegram
    telegram_file = await document.get_file()

    file_bytes = await telegram_file.download_as_bytearray()

    title = None
    author = None

    # -----------------------------------------------------
    # PDF
    # -----------------------------------------------------

    if extension == "pdf":

        title, author = extract_pdf_info(
            bytes(file_bytes)
        )

    # -----------------------------------------------------
    # EPUB
    # -----------------------------------------------------

    elif extension == "epub":

        title, author = extract_epub_info(
            bytes(file_bytes)
        )

    # Legenda original do post
    original_caption = message.caption or ""

    caption = create_book_caption(
        title,
        author,
        original_caption
    )

    # Envia para o grupo
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
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Erro no bot:",
        exc_info=context.error
    )


# =========================================================
# INICIA BOT
# =========================================================

def main():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN não configurado."
        )

    if not DESTINATION_CHAT_ID:

        raise ValueError(
            "DESTINATION_CHAT_ID não configurado."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Fotos
    application.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_photo
        )
    )

    # Figurinhas
    application.add_handler(
        MessageHandler(
            filters.Sticker.ALL,
            handle_sticker
        )
    )

    # PDF / EPUB
    application.add_handler(
        MessageHandler(
            filters.Document.ALL,
            handle_document
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "🤖 TinkerBooks iniciado!"
    )

    application.run_polling(
        drop_pending_updates=False
    )


if __name__ == "__main__":
    main()
  
          
