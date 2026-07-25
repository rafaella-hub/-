from telethon import
TelegramClient, events
from telethon.tl.types import
DocumentAttributeFilename
from telethon import Button

import os
import tempfile

from pyPDF2 import PdfReader
from ebooklib import epub

 
# CONFIGURAÇÕES 
 
API_ID = 31778524
API_HASH = 699ad42a06f620e5c945e15d666b4ad8
BOT_TOKEN = 8988209710:AAHBy8I342_stEY6bUFDzvxucEUO3WTOmec
CANAL_ORIGEM = -1004353168693
GRUPO_DESTINO = -1003794052661

client = TelegramClient(
  "Selly",
  API_ID,
  API_HASH
@client.on(events
           .newMessage(chats=CANAL_ORIGEM))
  async def
  nova_publicacao(event):
    print("Nova publicação detectada!")
      mensagem = event.message

              if mensagem.text:
                print("Texto:", mensagem.test)
              if mensagem.media:
                print("Midia detectada!")
  print("Tinker urniverse iniciado")
  client.start()
  client.run_until_disconnected()

  
          
