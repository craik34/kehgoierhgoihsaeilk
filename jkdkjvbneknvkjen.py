# meta developer: @modwini
import asyncio
import random
import logging
from hikka import loader, utils
from telethon import events
from telethon.tl.patched import Message
import g4f

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMemoryMod(loader.Module):
    """AI-персона с памятью на основе g4f и Hikka Userbot."""

    strings = {
        "name": "Gpt4PersonaMemory",
        "ii_on": "🎭 AI-персона активна в этом чате.",
        "ii_off": "🎭 AI-персона отключена.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "thinking": "```думаю...```",
        "error": "❌ Ошибка: {}",
        "timeout": "❌ AI не ответил вовремя.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("persona_name", "крейк", lambda: "Имя AI-персоны."),
            loader.ConfigValue("g4f_model", "gpt-4", lambda: "Модель g4f (gpt-4, gpt-3.5-turbo и т.д.)"),
            loader.ConfigValue("history_depth", 20, lambda: "Макс. сообщений в истории."),
            loader.ConfigValue("min_delay", 1, lambda: "Мин. задержка ответа, сек."),
            loader.ConfigValue("max_delay", 3, lambda: "Макс. задержка ответа, сек."),
        )
        self.active_chats = {}
        self.chat_histories = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = db.get("Gpt4PersonaMemoryMod", "active_chats", {})
        self.chat_histories = db.get("Gpt4PersonaMemoryMod", "chat_histories", {})
        self.client.add_event_handler(self.on_new_message, events.NewMessage(incoming=True, outgoing=False))

    @loader.command("ii")
    async def toggle_ai(self, m: Message):
        chat_id = str(utils.get_chat_id(m))
        await m.delete()
        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await utils.answer(m, self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            await utils.answer(m, self.strings("ii_on"))
        self.db.set("Gpt4PersonaMemoryMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m = event.message
        chat_id = str(utils.get_chat_id(m))

        if not self.active_chats.get(chat_id, False):
            return
        if not m.text:
            return
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        persona_name = self.config["persona_name"]
        g4f_model = self.config["g4f_model"]
        history_depth = self.config["history_depth"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]

        self.chat_histories.setdefault(chat_id, [])

        self.chat_histories[chat_id].append({"role": "user", "content": m.text})
        if len(self.chat_histories[chat_id]) > history_depth:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-history_depth:]

        thinking_msg = await utils.answer(m, self.strings("thinking"))
        await asyncio.sleep(random.uniform(min_delay, max_delay))

        try:
            response = g4f.ChatCompletion.create(
                model=g4f_model,
                messages=self.chat_histories[chat_id],
                stream=False,
                timeout=30,
            )

            if isinstance(response, str):
                response_text = response
            elif isinstance(response, dict) and "choices" in response:
                response_text = response["choices"][0]["message"]["content"]
            else:
                response_text = "⚠️ Неизвестный ответ от AI."

            self.chat_histories[chat_id].append({"role": "assistant", "content": response_text})
            await utils.answer(thinking_msg, response_text)

        except asyncio.TimeoutError:
            await utils.answer(thinking_msg, self.strings("timeout"))
        except Exception as e:
            logger.error("Gpt4PersonaMemory Error", exc_info=True)
            await utils.answer(thinking_msg, self.strings("error").format(str(e)))

        self.db.set("Gpt4PersonaMemoryMod", "chat_histories", self.chat_histories)
