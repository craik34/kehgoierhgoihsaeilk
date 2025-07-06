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
class Gpt4PersonaRealUserMod(loader.Module):
    """AI-персона "Крейк" с реалистичным поведением Telegram-пользователя."""

    strings = {
        "name": "Gpt4PersonaRealUser",
        "ii_on": "✅ Крейк активен в этом чате.",
        "ii_off": "❌ Крейк отключён.",
        "error": "❌ Ошибка: {}",
        "timeout": "❌ AI не ответил вовремя.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("persona_name", "крейк", lambda: "Имя AI-персоны."),
            loader.ConfigValue("g4f_model", "gpt-4", lambda: "Модель g4f (gpt-4, gpt-3.5-turbo и т.д.)"),
            loader.ConfigValue("history_depth", 20, lambda: "Сколько сообщений хранить в истории."),
            loader.ConfigValue("min_delay", 1, lambda: "Мин. задержка перед ответом (сек)."),
            loader.ConfigValue("max_delay", 3, lambda: "Макс. задержка перед ответом (сек)."),
        )
        self.active_chats = {}
        self.chat_histories = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = db.get("Gpt4PersonaRealUserMod", "active_chats", {})
        self.chat_histories = db.get("Gpt4PersonaRealUserMod", "chat_histories", {})
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
        self.db.set("Gpt4PersonaRealUserMod", "active_chats", self.active_chats)

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

        # История
        self.chat_histories.setdefault(chat_id, [])
        self.chat_histories[chat_id].append(f"Пользователь: {m.text}")
        if len(self.chat_histories[chat_id]) > history_depth:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-history_depth:]

        # Имитируем "печатает..."
        async with self.client.action(m.chat_id, "typing"):
            await asyncio.sleep(random.uniform(min_delay, max_delay))

            try:
                # Создание полного промта
                prompt = "\n".join(self.chat_histories[chat_id]) + f"""

ты — {persona_name}, пользователь в телеграм, которому 18 лет (упоминай только если спросят). 
Отвечай коротко и как обычный пользователь Telegram.
На вопрос: {m.text}
"""

                # Запрос к g4f
                response = g4f.ChatCompletion.create(
                    model=g4f_model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                    timeout=30,
                )

                if isinstance(response, str):
                    reply = response.strip()
                elif isinstance(response, dict) and "choices" in response:
                    reply = response["choices"][0]["message"]["content"].strip()
                else:
                    reply = "⚠️ Что-то не так с ответом AI."

                # Добавляем в историю
                self.chat_histories[chat_id].append(f"{persona_name}: {reply}")
                await m.reply(reply)

            except asyncio.TimeoutError:
                await m.reply(self.strings("timeout"))
            except Exception as e:
                logger.error("Gpt4PersonaRealUserMod Error", exc_info=True)
                await m.reply(self.strings("error").format(str(e)))

        # Сохраняем историю
        self.db.set("Gpt4PersonaRealUserMod", "chat_histories", self.chat_histories)
