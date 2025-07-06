# meta developer: @modwini

__pip_deps__ = ["g4f"]

import asyncio
import random
import logging
import g4f # Импортируем только базовый пакет g4f

from telethon import events
from telethon.tl.patched import Message
from .. import loader, utils

logger = logging.getLogger(__name__)

@loader.tds
class G4fPersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны
    с использованием g4f (GPT4Free) для бесплатных запросов к GPT-3.5/GPT-4.
    """

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "ai_model",
                "gpt-4", # Установлено на gpt-4 по умолчанию
                lambda: self.strings("ai_model_h"),
                validator=loader.validators.String(),
            ),
            # Убран параметр ai_provider, т.к. теперь полагаемся на автовыбор g4f
            loader.ConfigValue(
                "persona_name",
                "крейк",
                lambda: self.strings("persona_name_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "persona_instructions",
                (
                    "Ты пользователь в телеграм с никнеймом '{persona_name}'. "
                    "Тебе 18 лет. Отвечай как 18-летний человек, используя маленькие буквы. "
                    "Упоминай свой никнейм и возраст только если тебя об этом специально спросят. "
                    "Будь краток в ответах."
                ),
                lambda: self.strings("persona_instructions_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "history_limit",
                30,
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
            loader.ConfigValue(
                "ai_timeout",
                90, # Увеличим таймаут для GPT-4, т.к. он может быть медленнее
                lambda: self.strings("ai_timeout_h"),
                validator=loader.validators.Integer(minimum=10, maximum=300),
            ),
        )
        self.active_chats = {}

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("G4fPersonaMod", "active_chats", {})

        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False)
        )
        
        # g4f.debug.logging = True # Можно включить для отладки, если есть проблемы

    strings = {
        "name": "G4fPersona",
        "ai_model_h": "Модель AI для использования (по умолчанию 'gpt-4'). Может быть нестабильна через бесплатные провайдеры.",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "persona_instructions_h": "Инструкции для AI по ответам. Используйте {persona_name} для подстановки имени.",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_timeout_h": "Таймаут (в секундах) для запроса к AI. Увеличьте, если ответы слишком долгие.",
        "ii_on": "🎭 Режим G4fPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим G4fPersona выключен.",
        "ii_deleted_confirm": "```Команда .ii удалена.```",
        # "processing": "```думаю...```", # Убрано
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_model_not_found": "❌ Ошибка: Модель '{ai_model}' не найдена или недоступна у бесплатных провайдеров. Попробуйте другую модель или подождите.",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время ({} сек.). Попробуйте снова.",
        "not_text": "G4fPersona отвечает только на текстовые сообщения.",
    }

    strings_ru = {
        "name": "G4fPersona",
        "ai_model_h": "Модель AI для использования (по умолчанию 'gpt-4'). Может быть нестабильна через бесплатные провайдеры.",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "persona_instructions_h": "Инструкции для AI по ответам. Используйте {persona_name} для подстановки имени.",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_timeout_h": "Таймаут (в секундах) для запроса к AI. Увеличьте, если ответы слишком долгие.",
        "ii_on": "🎭 Режим G4fPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим G4fPersona выключен.",
        "ii_deleted_confirm": "```Команда .ii удалена.```",
        # "processing": "```думаю...```", # Убрано
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_model_not_found": "❌ Ошибка: Модель '{ai_model}' не найдена или недоступна у бесплатных провайдеров. Попробуйте другую модель или подождите.",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время ({} сек.). Попробуйте снова.",
        "not_text": "G4fPersona отвечает только на текстовые сообщения.",
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Включает/выключает режим ответов от имени AI-персоны в текущем чате."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]

        await m.delete()
        
        temp_confirm_message = await m.client.send_message(chat_id, self.strings("ii_deleted_confirm"))
        await asyncio.sleep(2) 
        await temp_confirm_message.delete()


        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await utils.answer(m, self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            await utils.answer(m, self.strings("ii_on").format(persona_name))

        self.db.set("G4fPersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m = event.message

        if not m.is_private and not m.is_group:
            return

        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False):
            return

        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        if m.text and m.text.startswith(".ii"):
            return

        if not m.text:
            # Отвечаем на нетекстовые сообщения, но без попытки отправки в AI
            await utils.answer(m, self.strings("not_text"))
            return

        persona_name = self.config["persona_name"]
        persona_instructions = self.config["persona_instructions"].format(persona_name=persona_name)
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        ai_model = self.config["ai_model"]
        ai_timeout = self.config["ai_timeout"]

        try:
            chat_messages = []
            me_id = me.id

            messages_to_process = []
            async for msg in self.client.iter_messages(chat_id, limit=history_limit):
                if msg.text:
                    messages_to_process.append(msg)
            
            for msg in reversed(messages_to_process):
                role = "assistant" if msg.sender_id == me_id else "user"
                chat_messages.append({"role": role, "content": msg.text})
            
            messages_for_ai = [
                {"role": "system", "content": persona_instructions}
            ] + chat_messages

            messages_for_ai.append({"role": "user", "content": m.text})

            # Случайная задержка перед запросом к AI
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            full_response_text = ""
            try:
                response_generator = g4f.ChatCompletion.create_async(
                    model=ai_model,
                    messages=messages_for_ai,
                    # provider=None - g4f по умолчанию сам выберет провайдера
                    stream=True,
                    timeout=ai_timeout
                )
                
                async for chunk in response_generator:
                    if chunk:
                        full_response_text += chunk
                
                if full_response_text:
                    # Отправляем ответ сразу, без редактирования "думаю..."
                    await m.reply(full_response_text) # Отвечаем на сообщение пользователя
                else:
                    logger.warning(f"G4fPersonaMod: Received empty response for model {ai_model}")
                    await m.reply(self.strings("error_processing").format("Пустой ответ от AI."))

            except g4f.errors.ModelNotFoundError:
                logger.error(f"G4fPersonaMod: ModelNotFound error for model: {ai_model}")
                await m.reply(self.strings("error_model_not_found").format(ai_model=ai_model))
            except asyncio.TimeoutError:
                logger.error(f"G4fPersonaMod: Timeout error for model: {ai_model}")
                await m.reply(self.strings("error_timeout").format(ai_timeout))
            except Exception as e:
                logger.error(f"G4fPersonaMod: General error getting response from g4f: {e}", exc_info=True)
                await m.reply(self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"G4fPersonaMod: Error in listener main block: {e}", exc_info=True)
            await m.reply(self.strings("error_processing").format(e))
