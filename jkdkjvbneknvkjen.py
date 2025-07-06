# meta developer: @modwini

__pip_deps__ = ["g4f"] # <-- ИСПРАВЛЕНО! Теперь правильно указывает на пакет 'g4f'

import asyncio
import random
import logging
import g4f 
from g4f.Provider import Liaobots, FreeGpt, Bing # Примеры провайдеров, можете добавить другие из документации g4f

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
                "gpt-3.5-turbo", # Или "gpt-4", "palm" и т.д. в зависимости от доступности в g4f
                lambda: self.strings("ai_model_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "ai_provider",
                "", # Оставьте пустым для автовыбора или укажите имя провайдера, например "Liaobots", "FreeGpt"
                lambda: self.strings("ai_provider_h"),
                validator=loader.validators.String(),
            ),
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
                60,
                lambda: self.strings("ai_timeout_h"),
                validator=loader.validators.Integer(minimum=10, maximum=300),
            ),
        )
        self.active_chats = {}  # {chat_id: True/False} - для отслеживания активных чатов

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("G4fPersonaMod", "active_chats", {})

        # Регистрируем обработчик событий для новых входящих сообщений
        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False) # incoming=True, outgoing=False - чтобы слушать только чужие сообщения
        )
        
        # Включаем логирование g4f для отладки, если нужно
        # g4f.debug.logging = True

    strings = {
        "name": "G4fPersona",
        "ai_model_h": "Модель AI для использования (например, 'gpt-3.5-turbo', 'gpt-4'). Проверяйте доступные модели в документации g4f.",
        "ai_provider_h": "Опционально: Имя конкретного провайдера g4f (например, 'Liaobots', 'FreeGpt', 'Bing'). Оставьте пустым для автовыбора. Убедитесь, что провайдер поддерживает выбранную модель.",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "persona_instructions_h": "Инструкции для AI по ответам. Используйте {persona_name} для подстановки имени.",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_timeout_h": "Таймаут (в секундах) для запроса к AI. Увеличьте, если ответы слишком долгие.",
        "ii_on": "🎭 Режим G4fPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим G4fPersona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_provider": "❌ Ошибка: Указанный провайдер '{}' не найден или недействителен. Пожалуйста, проверьте имя провайдера или оставьте поле пустым для автовыбора.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время ({} сек.). Попробуйте снова.",
        "not_text": "G4fPersona отвечает только на текстовые сообщения.",
        "not_supported": "❌ Выбранная модель '{}' не поддерживается указанным провайдером '{}'. Попробуйте другой провайдер или модель."
    }

    strings_ru = {
        "name": "G4fPersona",
        "ai_model_h": "Модель AI для использования (например, 'gpt-3.5-turbo', 'gpt-4'). Проверяйте доступные модели в документации g4f.",
        "ai_provider_h": "Опционально: Имя конкретного провайдера g4f (например, 'Liaobots', 'FreeGpt', 'Bing'). Оставьте пустым для автовыбора. Убедитесь, что провайдер поддерживает выбранную модель.",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "persona_instructions_h": "Инструкции для AI по ответам. Используйте {persona_name} для подстановки имени.",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_timeout_h": "Таймаут (в секундах) для запроса к AI. Увеличьте, если ответы слишком долгие.",
        "ii_on": "🎭 Режим G4fPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим G4fPersona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_provider": "❌ Ошибка: Указанный провайдер '{}' не найден или недействителен. Пожалуйста, проверьте имя провайдера или оставьте поле пустым для автовыбора.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время ({} сек.). Попробуйте снова.",
        "not_text": "G4fPersona отвечает только на текстовые сообщения.",
        "not_supported": "❌ Выбранная модель '{}' не поддерживается указанным провайдером '{}'. Попробуйте другой провайдер или модель."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Включает/выключает режим ответов от имени AI-персоны в текущем чате."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]

        # Удаляем сообщение с командой сразу
        await m.delete()
        # Отправляем подтверждение об удалении
        await utils.answer(m, self.strings("ii_deleted"))

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
            return  # Режим не активен в этом чате

        # Игнорируем сообщения от самого бота (вашего юзербота Hikka)
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        if m.text and m.text.startswith(".ii"):
            return  # Игнорируем саму команду .ii, чтобы избежать петли

        if not m.text:
            await utils.answer(m, self.strings("not_text"))
            return  # Отвечаем только на текстовые сообщения

        persona_name = self.config["persona_name"]
        persona_instructions = self.config["persona_instructions"].format(persona_name=persona_name)
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        ai_model = self.config["ai_model"]
        ai_provider_name = self.config["ai_provider"]
        ai_timeout = self.config["ai_timeout"]

        # Получаем объект провайдера g4f
        provider_obj = None
        if ai_provider_name:
            provider_obj = getattr(g4f.Provider, ai_provider_name, None)
            if not provider_obj:
                logger.error(f"Invalid g4f provider specified: {ai_provider_name}")
                await utils.answer(m, self.strings("error_provider").format(ai_provider_name))
                return
            # Дополнительная проверка на поддержку модели провайдером (не все провайдеры универсальны)
            # Примечание: Атрибуты 'supports_gpt_4' и 'supports_gpt_35_turbo' могут отсутствовать
            # у некоторых провайдеров в g4f, это лишь пример проверки.
            # Лучше всего опираться на актуальную документацию g4f или тестировать.
            if ai_model == "gpt-4" and not getattr(provider_obj, 'supports_gpt_4', False):
                 await utils.answer(m, self.strings("not_supported").format(ai_model, ai_provider_name))
                 return
            elif ai_model == "gpt-3.5-turbo" and not getattr(provider_obj, 'supports_gpt_35_turbo', False):
                 await utils.answer(m, self.strings("not_supported").format(ai_model, ai_provider_name))
                 return

        try:
            # Получаем историю чата для контекста в формате g4f (OpenAI roles)
            chat_messages = []
            me_id = me.id # ID вашего юзербота

            # Fetch messages in reverse chronological order and build history
            messages_to_process = []
            async for msg in self.client.iter_messages(chat_id, limit=history_limit):
                if msg.text:
                    messages_to_process.append(msg)
            
            # Process messages from oldest to newest for chronological context
            for msg in reversed(messages_to_process):
                # If the message is from me, it's a "persona" (assistant) response
                # Otherwise, it's a "user" message
                role = "assistant" if msg.sender_id == me_id else "user"
                chat_messages.append({"role": role, "content": msg.text})
            
            # Добавляем системные инструкции для AI-персоны
            messages_for_ai = [
                {"role": "system", "content": persona_instructions}
            ] + chat_messages

            # Добавляем текущее сообщение пользователя
            messages_for_ai.append({"role": "user", "content": m.text})

            # Случайная задержка
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Отправляем "думаю..." сообщение
            thinking_message = await utils.answer(m, self.strings("processing"))

            full_response_text = ""
            try:
                # Отправляем запрос в g4f
                response_generator = g4f.ChatCompletion.create_async(
                    model=ai_model,
                    messages=messages_for_ai,
                    provider=provider_obj, # Будет None, если не указан или недействителен (автовыбор)
                    stream=True, # Используем стриминг, чтобы получать ответ по частям
                    timeout=ai_timeout
                )
                
                # Собираем ответ по частям
                async for chunk in response_generator:
                    if chunk:
                        full_response_text += chunk
                        # Можно тут редактировать thinking_message, но это может вызвать флуд-лимиты.
                        # utils.answer уже сам редактирует, так что просто соберем полный текст.
                        # Для полноценного стриминга в реальном времени, нужно доработать.
                        pass 

                # Редактируем сообщение "думаю..." на полный ответ от AI
                if full_response_text:
                    await utils.answer(thinking_message, full_response_text)
                else:
                    await utils.answer(thinking_message, self.strings("error_processing").format("Пустой ответ от AI."))

            except asyncio.TimeoutError:
                await utils.answer(thinking_message, self.strings("error_timeout").format(ai_timeout))
            except Exception as e:
                logger.error(f"Error getting response from g4f: {e}", exc_info=True)
                await utils.answer(thinking_message, self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"Error in G4fPersonaMod listener: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(e))
