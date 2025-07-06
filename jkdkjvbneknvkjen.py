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
class Gpt4PersonaTyping(loader.Module):
    """AI-персона Крэйк с памятью и реалистичной подачей под Telegram-юзера."""

    strings = {
        "name": "Gpt4PersonaTyping",
        "activated": "🟢 Крэйк активен в этом чате.",
        "deactivated": "🔴 Крэйк отключён.",
        "error": "❌ Ошибка: {}",
        "timeout": "⚠️ Крэйк задумался слишком долго.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("persona_name", "крейк", lambda: "Имя персонажа."),
            loader.ConfigValue("g4f_model", "gpt-4", lambda: "g4f модель (gpt-4, gpt-3.5-turbo и т.д.)"),
            loader.ConfigValue("history_limit", 20, lambda: "Сколько сообщений сохранять в истории."),
            loader.ConfigValue("min_delay", 1, lambda: "Мин. задержка перед ответом."),
            loader.ConfigValue("max_delay", 3, lambda: "Макс. задержка перед ответом."),
        )
        self.active_chats = {}
        self.chat_histories = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = db.get("Gpt4PersonaTyping", "active_chats", {})
        self.chat_histories = db.get("Gpt4PersonaTyping", "chat_histories", {})
        self.client.add_event_handler(self.on_new_message, events.NewMessage(incoming=True, outgoing=False))

    @loader.command("ii")
    async def toggle_ai(self, m: Message):
        chat_id = str(utils.get_chat_id(m))
        await m.delete()
        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await utils.answer(m, self.strings("deactivated"))
        else:
            self.active_chats[chat_id] = True
            await utils.answer(m, self.strings("activated"))
        self.db.set("Gpt4PersonaTyping", "active_chats", self.active_chats)

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

        name = self.config["persona_name"]
        model = self.config["g4f_model"]
        max_history = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]

        # История чата
        self.chat_histories.setdefault(chat_id, [])
        self.chat_histories[chat_id].append({"role": "user", "content": m.text})
        self.chat_histories[chat_id] = self.chat_histories[chat_id][-max_history:]

        # Промт-инструкция
        full_dialog = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_histories[chat_id]])
        system_prompt = (
            f"{full_dialog}\n\n\n"
            f"ты - {name}, пользователь в телеграм которому 18 лет (упоминай только если спросят), "
            f"отвечай коротко и как пользователь в телеграм на вопрос: {m.text}"
        )

        try:
            # Эмуляция "печатает…"
            typing = await m.respond("⌨️ печатает...")
            await asyncio.sleep(random.uniform(min_delay, max_delay))

            response = g4f.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt}
                ],
                stream=False,
                timeout=30,
            )

            if isinstance(response, str):
                response_text = response.strip()
            elif isinstance(response, dict) and "choices" in response:
                response_text = response["choices"][0]["message"]["content"].strip()
            else:
                response_text = "?"

            # Сохраняем ответ в историю
            self.chat_histories[chat_id].append({"role": "assistant", "content": response_text})
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-max_history:]

            await typing.edit(response_text)

        except asyncio.TimeoutError:
            await m.respond(self.strings("timeout"))
        except Exception as e:
            logger.exception("Ошибка в Gpt4PersonaTyping")
            await m.respond(self.strings("error").format(str(e)))

        # Сохраняем историю
        self.db.set("Gpt4PersonaTyping", "chat_histories", self.chat_histories)
