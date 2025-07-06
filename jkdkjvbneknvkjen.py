# meta developer: @modwini
#
# Полностью переработанный модуль для ответов от лица AI-персоны
# с использованием g4f (GPT-4 Free).
# Устранены все известные ошибки и добавлена отказоустойчивость.

import asyncio
import random
import logging
import g4f

from hikka import loader, utils
from telethon import events
from telethon.tl.patched import Message

# Настройка логирования для g4f, чтобы не засорять консоль
g4f.debug.logging = False

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMod(loader.Module):
    """
    Отвечает в чате от имени AI-персоны, используя g4f (gpt4free).
    """

    strings = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк').",
        "history_limit_h": "Количество последних сообщений для контекста (5-100).",
        "min_delay_h": "Мин. задержка перед ответом AI (сек).",
        "max_delay_h": "Макс. задержка перед ответом AI (сек).",
        "model_h": "Модель для использования. Пример: g4f.models.gpt_4, g4f.models.gpt_3_5_turbo.",
        "ii_on": "🎭 <b>Режим Gpt4Persona включен.</b>\nТеперь я отвечаю в этом чате как <code>{}</code>.",
        "ii_off": "🎭 <b>Режим Gpt4Persona выключен.</b>",
        "processing": "<code>🤔 думаю...</code>",
        "error_processing": "❌ <b>Произошла ошибка при обработке запроса:</b>\n<code>{}</code>",
        "history_error": "⚠️ Не удалось загрузить историю чата, отвечаю без контекста.",
        "not_text": "👀 Я отвечаю только на текстовые сообщения.",
        "_cmd_doc_ii": "Включить/выключить режим ответов от имени AI в текущем чате.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "persona_name",
                "крейк",
                lambda: self.strings("persona_name_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "model",
                "gpt-4",
                lambda: self.strings("model_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "history_limit",
                25,
                lambda: self.strings("history_limit_h"),
                validator=loader.validators.Integer(minimum=5, maximum=100),
            ),
            loader.ConfigValue(
                "min_delay",
                2,
                lambda: self.strings("min_delay_h"),
                validator=loader.validators.Integer(minimum=0, maximum=10),
            ),
            loader.ConfigValue(
                "max_delay",
                5,
                lambda: self.strings("max_delay_h"),
                validator=loader.validators.Integer(minimum=0, maximum=10),
            ),
        )
        self.active_chats = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.me = await client.get_me()
        self.active_chats = self.db.get("Gpt4PersonaMod", "active_chats", {})
        
        # Правильная регистрация обработчика входящих сообщений
        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False)
        )

    @loader.command()
    async def ii(self, m: Message):
        """Включить/выключить режим ответов от имени AI."""
        chat_id = utils.get_chat_id(m)
        
        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await utils.answer(m, self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            persona_name = self.config["persona_name"]
            await utils.answer(m, self.strings("ii_on").format(persona_name))

        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event: events.NewMessage.Event):
        """Обрабатывает новые входящие сообщения."""
        m = event.message
        chat_id = utils.get_chat_id(m)

        # --- Основные проверки для предотвращения срабатывания ---
        if not self.active_chats.get(chat_id, False):
            return

        if m.sender_id == self.me.id:
            return

        # Игнорируем команды и сообщения без текста
        if not m.text or m.text.startswith(self.get_prefix()):
            return
            
        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        
        history_string = ""
        # --- Безопасный сбор истории чата ---
        try:
            history_messages = []
            async for historic_msg in self.client.iter_messages(chat_id, limit=history_limit):
                # Проверяем, что сообщение не пустое и содержит текст
                if historic_msg and historic_msg.text:
                    sender = await historic_msg.get_sender()
                    sender_name = persona_name if historic_msg.out else (
                        sender.first_name or sender.username or f"Пользователь_{sender.id}"
                    )
                    history_messages.append(f"{sender_name}: {historic_msg.text}")
            
            # Переворачиваем историю для правильного хронологического порядка
            history_string = "\n".join(reversed(history_messages))
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            await self.client.send_message(chat_id, self.strings("history_error"))
            # Продолжаем без истории

        # --- Формирование промпта для AI ---
        prompt = (
            f"Ты - пользователь Telegram с ником '{persona_name}'. Тебе 18 лет. "
            f"Ты общаешься в чате. Твоя задача - коротко и ёмко ответить на последнее сообщение "
            f"с учетом контекста предыдущего диалога. Отвечай всегда с маленькой буквы. "
            f"Не упоминай, что ты ИИ или ассистент. Будь немного дерзким и неформальным, как обычный парень."
            f"\n\n--- КОНТЕКСТ ДИАЛОГА ---\n{history_string}\n\n"
            f"--- ПОСЛЕДНЕЕ СООБЩЕНИЕ, НА КОТОРОЕ НАДО ОТВЕТИТЬ ---\n"
            f"{m.sender.first_name or 'Пользователь'}: {m.text}"
        )

        # --- Отправка запроса и получение ответа ---
        try:
            # Случайная задержка для имитации человеческого поведения
            delay = random.uniform(self.config["min_delay"], self.config["max_delay"])
            await asyncio.sleep(delay)
            
            # Отправляем сообщение "думаю..." и сохраняем его для редактирования
            thinking_message = await utils.answer(m, self.strings("processing"))

            # Асинхронный запрос к g4f
            response_text = await g4f.ChatCompletion.create_async(
                model=self.config["model"],
                messages=[{"role": "user", "content": prompt}],
                # provider=g4f.Provider.GeekGpt  # Можно указать конкретный, если нужно
            )
            
            # Редактируем сообщение "думаю..." на ответ от AI
            if response_text:
                await utils.answer(thinking_message, response_text)
            else:
                await utils.answer(thinking_message, self.strings("error_processing").format("AI вернул пустой ответ."))

        except Exception as e:
            logger.error(f"Error processing g4f request: {e}", exc_info=True)
            # Если возникла ошибка, редактируем "думаю..." на сообщение об ошибке
            if 'thinking_message' in locals():
                await utils.answer(thinking_message, self.strings("error_processing").format(e))
            else:
                await utils.answer(m, self.strings("error_processing").format(e))
