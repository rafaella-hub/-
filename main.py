from telethon import TelegramClient, events
import os

# CONFIGURAÇÕES PELO RENDER
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

CANAL_ORIGEM = int(os.getenv("CANAL_ORIGEM"))
GRUPO_DESTINO = int(os.getenv("GRUPO_DESTINO"))


client = TelegramClient(
    "Selly",
    API_ID,
    API_HASH
)


@client.on(events.NewMessage(chats=CANAL_ORIGEM))
async def copiar_mensagem(event):

    print("Nova mensagem recebida no Tinker Universe")

    try:
        await client.forward_messages(
            GRUPO_DESTINO,
            event.message
        )

        print("Mensagem enviada para Tinker Books")

    except Exception as erro:
        print("Erro ao enviar:", erro)


print("Bot Tinker Universe iniciado!")

client.start(bot_token=BOT_TOKEN)
client.run_until_disconnected()


  
          
