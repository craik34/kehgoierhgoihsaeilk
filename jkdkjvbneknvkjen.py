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
        "generating_response": "...", # Изменено, чтобы не "думать"
        "error": "❌ Ошибка: {}",
        "timeout": "❌ AI не ответил вовремя.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue("persona_name", "крейк", lambda: "Имя AI-персоны."),
            loader.ConfigValue("g4f_model", "gpt-4", lambda: "Модель g4f (gpt-4, gpt-3.5-turbo и т.д.)"),
            loader.ConfigValue("history_depth", 30, lambda: "Макс. сообщений в истории."), # Увеличено до 30
            loader.ConfigValue("min_delay", 1, lambda: "Мин. задержка ответа, сек."),
            loader.ConfigValue("max_delay", 3, lambda: "Макс. задержка ответа, сек."),
            loader.ConfigValue("system_prompt",
                               "Ты - крейк, пользователь в Телеграм. Тебе 18 лет (упоминай свой возраст только если спросят). Отвечай коротко без занаков препинания используй маты отвечай с маленькой буквы, как обычный пользователь в Телеграм. Можешь писать маты и быть грубым если это необходимо.",
                               lambda: "Системный промпт для AI-персоны. Определяет её характер и стиль ответов."),
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
        
        # Определяем сообщение, которое будет отправлено
        message_to_send = ""
        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            message_to_send = self.strings("ii_off")
        else:
            self.active_chats[chat_id] = True
            message_to_send = self.strings("ii_on")
        
        # Сначала отправляем ответ
        await utils.answer(m, message_to_send)
        
        # Теперь удаляем исходное сообщение команды
        try:
            await m.delete()
        except Exception as e:
            logger.warning(f"Failed to delete command message: {e}")
            # Можно отправить сообщение о том, что не удалось удалить,
            # но обычно это не критично для работы модуля.
            # await utils.answer(m, self.strings("ii_deleted")) # Или что-то подобное

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

        persona_name = self.config["persona_name"] # Эта переменная не используется, но оставлена на случай если понадобится
        g4f_model = self.config["g4f_model"]
        history_depth = self.config["history_depth"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        system_prompt = self.config["system_prompt"]

        self.chat_histories.setdefault(chat_id, [])

        # Добавляем текущее сообщение пользователя в историю
        self.chat_histories[chat_id].append({"role": "user", "content": m.text})
        
        # Обрезаем историю, оставляя только последние `history_depth` сообщений
        if len(self.chat_histories[chat_id]) > history_depth:
            self.chat_histories[chat_id] = self.chat_histories[chat_id][-history_depth:]

        # Собираем сообщения для отправки AI, включая системный промпт
        messages_for_ai = [{"role": "system", "content": system_prompt}] + self.chat_histories[chat_id]

        # Отображаем индикатор генерации ответа
        # Используем m.reply() для нового сообщения, чтобы не зависеть от редактирования исходного
        generating_msg = await m.reply(self.strings("generating_response"))
        await asyncio.sleep(random.uniform(min_delay, max_delay)) # Небольшая задержка для имитации "живого" ответа

        try:
            response = g4f.ChatCompletion.create(
                model=g4f_model,
                messages=messages_for_ai, # Отправляем собранные сообщения
                stream=False,
                timeout=30,
            )

            if isinstance(response, str):
                response_text = response
            elif isinstance(response, dict) and "choices" in response:
                response_text = response["choices"][0]["message"]["content"]
            else:
                response_text = "⚠️ Неизвестный ответ от AI."
                logger.warning(f"Unexpected AI response format: {response}")


            # Добавляем ответ AI в историю чата
            self.chat_histories[chat_id].append({"role": "assistant", "content": response_text})
            
            # Редактируем сообщение с индикатором на фактический ответ
            await generating_msg.edit(response_text) # Используем .edit() на сообщении-индикаторе

        except asyncio.TimeoutError:
            await generating_msg.edit(self.strings("timeout"))
        except Exception as e:
            logger.error("Gpt4PersonaMemory Error", exc_info=True)
            await generating_msg.edit(self.strings("error").format(str(e)))

        # Сохраняем обновленную историю в базе данных
        self.db.set("Gpt4PersonaMemoryMod", "chat_histories", self.chat_histories)
