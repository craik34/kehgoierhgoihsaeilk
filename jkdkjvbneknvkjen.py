# meta developer: @modwini
import asyncio
import random
import logging
from hikka import loader, utils
from telethon import events
from telethon.tl.patched import Message

# Импортируем g4f
import g4f

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны "Крейк"
    с использованием GPT4Free (g4f).
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
                "g4f_model",
                "gpt-3.5-turbo", # Можно попробовать "gpt-4" или другие, если 3.5-turbo не работает
                lambda: self.strings("g4f_model_h"),
                validator=loader.validators.String(),
            ),
        )
        self.active_chats = {}  # {chat_id: True/False} - для отслеживания активных чатов

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("Gpt4PersonaMod", "active_chats", {})

        # Регистрируем обработчик событий для новых входящих сообщений
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
        "g4f_model_h": "Модель g4f для использования (например, 'gpt-3.5-turbo' или 'gpt-4').",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "no_history": "Не удалось получить историю диалога для контекста. Отвечаю без нее.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "g4f_model_h": "Модель g4f для использования (например, 'gpt-3.5-turbo' или 'gpt-4').",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "no_history": "Не удалось получить историю диалога для контекста. Отвечаю без нее.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Toggle Gpt4Persona for current chat."""
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

        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m = event.message

        # Проверяем, что сообщение пришло из личного чата, группы или канала
        if not m.is_private and not m.is_group and not m.is_channel:
            return

        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False):
            return  # Режим не активен в этом чате

        # Игнорируем сообщения от самого бота (вашего юзербота Hikka)
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        # Игнорируем саму команду .ii, чтобы избежать петли
        if m.text and m.text.lower().startswith(".ii"):
            return

        if not m.text:
            # Отвечаем только на текстовые сообщения
            return

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        g4f_model = self.config["g4f_model"]

        try:
            # Получаем историю чата для контекста
            history_messages = []
            try:
                async for msg_in_history in self.client.iter_messages(chat_id, limit=history_limit):
                    # Проверяем, что сообщение содержит текст и не является None
                    if msg_in_history.text:
                        sender_name = ""
                        
                        # Получаем объект отправителя безопасно
                        sender = await msg_in_history.get_sender()
                        
                        if msg_in_history.sender_id == me.id:
                            sender_name = persona_name
                        elif sender: # Если объект отправителя получен
                            sender_name = sender.first_name or sender.username
                        
                        # Если имя отправителя все еще не определено, пытаемся получить из чата
                        if not sender_name:
                            chat_obj = await msg_in_history.get_chat()
                            if chat_obj and hasattr(chat_obj, 'title'):
                                sender_name = chat_obj.title
                            elif msg_in_history.sender_id: # Если есть только ID отправителя
                                sender_name = f"Пользователь_{msg_in_history.sender_id}"
                            else: # Крайний случай, если ничего не удалось получить
                                sender_name = "Неизвестный"

                        history_messages.append(f"{sender_name}: {msg_in_history.text}")
            except Exception as e:
                logger.warning(f"Failed to get chat history: {e}", exc_info=True)
                await utils.answer(m, self.strings("no_history"))
                history_messages = [] # Очищаем историю, чтобы не передавать некорректные данные

            # Переворачиваем историю, чтобы старые сообщения были в начале
            history_string = "\n".join(reversed(history_messages)) if history_messages else ""

            # Формируем промпт
            prompt_parts = []
            if history_string:
                prompt_parts.append(f"История диалога:\n{history_string}")
            
            prompt_parts.append(
                f"Ты пользователь в телеграм с никнеймом {persona_name}. "
                f"Отвечай как 18-летний человек, пиши с маленькой буквы. "
                f"Упоминай никнейм и возраст только если тебя об этом спросят. "
                f"Твой ответ должен быть коротким и по существу. "
                f"Ответь на следующее сообщение: {m.text}"
            )
            
            final_prompt = "\n\n".join(prompt_parts)

            # Случайная задержка
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Отправляем "думаю..." сообщение
            thinking_message = await utils.answer(m, self.strings("processing"))

            try:
                # Отправляем запрос в g4f
                response = g4f.ChatCompletion.create(
                    model=g4f_model,
                    messages=[{"role": "user", "content": final_prompt}],
                    stream=False,
                    timeout=30
                )
                response_text = response

                # Редактируем сообщение "думаю..." на ответ от AI
                await utils.answer(thinking_message, response_text)

            except asyncio.TimeoutError:
                await utils.answer(thinking_message, self.strings("error_timeout"))
            except Exception as e:
                logger.error(f"Error getting response from g4f: {e}", exc_info=True)
                await utils.answer(thinking_message, self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"Error in Gpt4PersonaMod listener: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(e))
