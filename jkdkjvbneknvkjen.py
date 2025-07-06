# meta developer: @modwini

from .. import loader, utils
from asyncio import sleep
import logging
import random
from telethon import events
from telethon.tl.patched import Message
import g4f # Импортируем библиотеку g4f

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны "Крейк"
    с использованием бесплатных API GPT-4 через g4f.
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
        )
        self.active_chats = {}  # {chat_id: True/False} - для отслеживания активных чатов
        self.client = None # Инициализируем client здесь

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("Gpt4PersonaMod", "active_chats", {})

        # Регистрируем обработчик событий для новых входящих сообщений
        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False) # Слушаем только чужие сообщения
        )

    strings = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "no_reply_found": "Не удалось получить ответ от модели. Попробуйте другой запрос или проверьте, работает ли модель.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "Gpt4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "no_reply_found": "Не удалось получить ответ от модели. Попробуйте другой запрос или проверьте, работает ли модель.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
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

        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

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
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]

        try:
            # Получаем историю чата для контекста
            messages_for_g4f = []
            
            # Телеграм API возвращает сообщения от новых к старым, нам нужно наоборот для контекста.
            # Поэтому сначала собираем, потом переворачиваем.
            fetched_messages = []
            async for msg in self.client.iter_messages(chat_id, limit=history_limit):
                if msg.text:
                    fetched_messages.append(msg)
            
            # Переворачиваем сообщения, чтобы они были в хронологическом порядке (старые -> новые)
            for msg in reversed(fetched_messages):
                # Определяем роль отправителя для GPT
                if msg.sender_id == me.id:
                    role = "assistant" # Если сообщение от нас, это наш "ответ" в истории
                    content = msg.text
                else:
                    role = "user"
                    # Если нужно добавить имя отправителя в содержание сообщения для пользователя
                    # sender_name = msg.sender.first_name or msg.sender.username or f"Пользователь_{msg.sender_id}"
                    # content = f"{sender_name}: {msg.text}"
                    content = msg.text # Оставляем только текст, чтобы не путать модель именами, если это не нужно для роли.

                messages_for_g4f.append({"role": role, "content": content})

            # Добавляем текущее сообщение пользователя в конец истории для запроса
            # Это будет последним сообщением пользователя в диалоге
            user_message_text = m.text
            messages_for_g4f.append({"role": "user", "content": user_message_text})

            # Добавляем системный промт в начало, если это необходимо для персоны
            # Важно: системный промт должен идти первым
            system_prompt = (
                f"Ты пользователь Telegram с никнеймом {persona_name}. "
                f"Отвечай как 18-летний человек, используя небольшой регистр. "
                f"Упоминай свой никнейм и возраст только если тебя об этом спросят. "
                f"Отвечай коротко и по существу."
            )
            # Вставляем системный промт в начало списка сообщений
            messages_for_g4f.insert(0, {"role": "system", "content": system_prompt})

            # Случайная задержка
            delay = random.uniform(min_delay, max_delay)
            await sleep(delay) # Используем asyncio.sleep

            # Отправляем "думаю..." сообщение
            thinking_message = await utils.answer(m, self.strings("processing"))

            try:
                # Отправляем запрос в g4f (GPT-4)
                # g4f.debug.logging = True # Для отладки, если нужно
                # g4f.check_version = False # Отключаем проверку версии, если она вызывает ошибки

                response = g4f.ChatCompletion.create(
                    model="gpt-4", # Выбираем модель gpt-4
                    messages=messages_for_g4f,
                    stream=False, # Не используем стриминг для однократного ответа
                    timeout=60 # Увеличиваем таймаут на всякий случай
                )

                if response:
                    response_text = response
                    # Редактируем сообщение "думаю..." на ответ от AI
                    await utils.answer(thinking_message, response_text)
                else:
                    await utils.answer(thinking_message, self.strings("no_reply_found"))

            except Exception as e:
                logger.error(f"Error getting response from g4f: {e}", exc_info=True)
                await utils.answer(thinking_message, self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"Error in Gpt4PersonaMod listener: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(e))
