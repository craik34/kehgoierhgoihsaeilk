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
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны "Крейк"
    с использованием G4F (GPT-4).
    """

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "persona_name",
                "крейк",
                lambda: self.strings("persona_name_h"),
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
                "model_name",
                "gpt-4",  # Используем gpt-4 по умолчанию, как запрашивалось
                lambda: self.strings("model_name_h"),
                validator=loader.validators.String(),
            )
        )
        self.active_chats = {}  # {chat_id: True/False} - для отслеживания активных чатов

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("Gpt4PersonaMod", "active_chats", {})

        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False)
        )

    strings = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "model_name_h": "Имя модели G4F для использования (например, 'gpt-4', 'gpt-3.5-turbo').",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "`⏳ .ii` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "model_name_h": "Имя модели G4F для использования (например, 'gpt-4', 'gpt-3.5-turbo').",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "`⏳ .ii` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Toggle Gpt4 persona for current chat."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]

        # Отправляем сообщение-подтверждение ДО удаления, чтобы избежать MessageIdInvalidError
        status_message = await utils.answer(m, self.strings("ii_deleted"))
        # Теперь удаляем исходное сообщение
        await m.delete()

        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await utils.answer(status_message, self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            await utils.answer(status_message, self.strings("ii_on").format(persona_name))

        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m = event.message

        if not m.is_private and not m.is_group:
            return

        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False):
            return  # Режим не активен в этом чате

        me = await self.client.get_me()
        if m.sender_id == me.id:
            return # Игнорируем сообщения от самого юзербота

        # Проверяем, что сообщение является текстовым, и игнорируем команды .ii
        if not m.text:
            return # Игнорируем нетекстовые сообщения
        if m.text and m.text.startswith(self.get_prefix() + "ii"): # Используем get_prefix() для проверки команды
            return # Игнорируем саму команду .ii, чтобы избежать петли

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        model_name = self.config["model_name"]

        try:
            # Получаем историю чата для контекста
            history_messages_list = []
            # Используем reversed() для правильного порядка (старые -> новые)
            async for msg in self.client.iter_messages(chat_id, limit=history_limit):
                if msg.text: # Убедимся, что сообщение содержит текст, чтобы избежать AttributeError
                    sender_entity = await msg.get_sender() # Получаем объект отправителя
                    if sender_entity:
                        sender_name = persona_name if msg.sender_id == me.id else (sender_entity.first_name or sender_entity.username or f"Пользователь_{msg.sender_id}")
                        history_messages_list.append(f"{sender_name}: {msg.text}")
                    else:
                        # Если sender_entity None (редко, но бывает), используем ID
                        sender_name = persona_name if msg.sender_id == me.id else f"Пользователь_{msg.sender_id}"
                        history_messages_list.append(f"{sender_name}: {msg.text}")

            # G4F ожидает список словарей для истории
            messages_for_g4f = []
            for item in history_messages_list:
                if item.startswith(f"{persona_name}:"):
                    messages_for_g4f.append({"role": "assistant", "content": item.replace(f"{persona_name}: ", "")})
                else:
                    # Извлекаем имя пользователя и его сообщение
                    parts = item.split(": ", 1)
                    if len(parts) == 2:
                        user_name = parts[0]
                        user_content = parts[1]
                        messages_for_g4f.append({"role": "user", "content": f"{user_name}: {user_content}"})
                    else:
                        messages_for_g4f.append({"role": "user", "content": item}) # Fallback

            # Добавляем текущее сообщение пользователя в конец истории
            current_sender_entity = await m.get_sender()
            current_sender_name = current_sender_entity.first_name or current_sender_entity.username or f"Пользователь_{m.sender_id}"
            messages_for_g4f.append({"role": "user", "content": f"{current_sender_name}: {m.text}"})

            # Добавляем системное сообщение для персоны
            messages_for_g4f.insert(0, {
                "role": "system",
                "content": f"Ты пользователь телеграм с никнеймом {persona_name}. Отвечай как 18-летний человек, "
                           f"пиши с маленькой буквы. Упоминай никнейм и возраст, только если тебя об этом спросят. "
                           f"Коротко отвечай на последний вопрос в диалоге, соблюдая стиль."
            })
            
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            thinking_message = await utils.answer(m, self.strings("processing"))

            try:
                # Отправляем запрос в G4F
                response = ""
                # G4F.ChatCompletion.create может вернуть строку или итератор, если stream=True.
                # Если модель не поддерживает стриминг, она вернет сразу строку.
                # Поэтому обрабатываем оба случая.
                g4f_response = g4f.ChatCompletion.create(
                    model=model_name,
                    messages=messages_for_g4f,
                    stream=True, # Попробуем стриминг
                    # proxy="http://host:port", # Если нужен прокси, можно добавить сюда
                    # timeout=60 # Таймаут по умолчанию 120, можно изменить
                )
                
                if isinstance(g4f_response, str):
                    response = g4f_response
                else:
                    for message_chunk in g4f_response:
                        response += message_chunk
                        # Можно добавить небольшой таймаут для плавности обновления
                        # await asyncio.sleep(0.05) 
                        # await utils.answer(thinking_message, response) # Обновлять сообщение по мере получения

                await utils.answer(thinking_message, response)

            except Exception as e:
                logger.error(f"Error getting response from G4F: {e}", exc_info=True)
                if "Model not found" in str(e):
                    error_msg = f"❌ Ошибка: Модель '{model_name}' не найдена или не поддерживается. Попробуйте другую модель в конфиге."
                elif "timeout" in str(e).lower():
                    error_msg = self.strings("error_timeout")
                else:
                    error_msg = self.strings("error_processing").format(e)
                await utils.answer(thinking_message, error_msg)

        except Exception as e:
            logger.error(f"Error in Gpt4PersonaMod listener: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(e))
