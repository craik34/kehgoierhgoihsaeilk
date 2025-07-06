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
class Gpt4PersonaMod(loader.Module):
    """AI-персона 'Крейк' с контекстом и короткими ответами."""

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("persona_name", "крейк", lambda: "Имя AI-персоны"),
            loader.ConfigValue("history_limit", 30, lambda: "Сколько сообщений использовать в истории", validator=loader.validators.Integer(5, 100)),
            loader.ConfigValue("min_delay", 1, lambda: "Минимальная задержка перед ответом", validator=loader.validators.Integer(0, 5)),
            loader.ConfigValue("max_delay", 2, lambda: "Максимальная задержка перед ответом", validator=loader.validators.Integer(0, 5)),
            loader.ConfigValue("g4f_model", "gpt-3.5-turbo", lambda: "Модель g4f (например, gpt-4)", validator=loader.validators.String())
        )
        self.active_chats = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("Gpt4PersonaMod", "active_chats", {})
        self.client.add_event_handler(self.on_new_message, events.NewMessage(incoming=True, outgoing=False))

    strings = {
        "name": "Gpt4Persona",
        "ii_on": "🟢 Крейк активен в этом чате.",
        "ii_off": "🔴 Крейк отключён.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "error_processing": "❌ Ошибка: {}",
        "error_timeout": "⏳ Время ожидания AI истекло.",
        "no_history": "⚠️ История не получена. Отвечаю без неё.",
        "_cmd_doc_ii": "Вкл/выкл ответы Крейка в этом чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        chat_id = utils.get_chat_id(m)
        await m.delete()
        if self.active_chats.get(chat_id):
            self.active_chats[chat_id] = False
            await utils.answer(m, self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            await utils.answer(m, self.strings("ii_on"))
        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m = event.message
        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False): return
        if not m.text: return
        me = await self.client.get_me()
        if m.sender_id == me.id: return
        if m.text.lower().startswith(".ii"): return

        persona_name = self.config["persona_name"]
        model = self.config["g4f_model"]
        limit = self.config["history_limit"]
        min_d = self.config["min_delay"]
        max_d = self.config["max_delay"]

        # Задержка, как будто человек печатает
        await asyncio.sleep(random.uniform(min_d, max_d))

        # История сообщений
        history_messages = []
        try:
            async for msg in self.client.iter_messages(chat_id, limit=limit):
                if msg.text:
                    sender = await msg.get_sender()
                    name = sender.first_name or sender.username or f"User_{msg.sender_id}"
                    if msg.sender_id == me.id:
                        name = persona_name
                    history_messages.append(f"{name}: {msg.text}")
        except Exception as e:
            logger.warning(f"Ошибка истории: {e}", exc_info=True)
            await utils.answer(m, self.strings("no_history"))

        history_text = "\n".join(reversed(history_messages)) if history_messages else ""

        prompt = (
            f"{history_text}\n\n\n"
            f"ты — {persona_name}, пользователь в телеграм которому 18 лет "
            f"(упоминай только если спросят). "
            f"отвечай коротко и как пользователь в телеграм на вопрос: {m.text}"
        )

        try:
            response = g4f.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                timeout=30
            )
            await utils.answer(m, response)

        except asyncio.TimeoutError:
            await utils.answer(m, self.strings("error_timeout"))
        except Exception as e:
            logger.error(f"Ошибка g4f: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(str(e)))
