
import asyncio
import random
import logging
from hikka import loader, utils
# !!! ВАЖНО: Добавьте импорт events из telethon !!!
from telethon import events
from telethon.tl.patched import Message
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

@loader.tds
class GeminiPersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны "Крейк"
    с использованием Google Gemini.
    """

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "gemini_api_key",
                "AIzaSyCQijR-EI9Ird5YFPn1a2j3WQVH0g0qGPo",  # !! ЗАМЕНИТЕ НА СВОЙ КЛЮЧ !!
                lambda: self.strings("api_key_h"),
                validator=loader.validators.String(),
            ),
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
        self.gemini_client = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.active_chats = self.db.get("GeminiPersonaMod", "active_chats", {})
        self._init_gemini_client()

        # --- ВАЖНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ ---
        # Регистрируем обработчик событий для новых входящих сообщений
        self.client.add_event_handler(
            self.on_new_message,
            events.NewMessage(incoming=True, outgoing=False) # incoming=True, outgoing=False - чтобы слушать только чужие сообщения
        )
        # --- КОНЕЦ ВАЖНОГО ИЗМЕНЕНИЯ ---

    def _init_gemini_client(self):
        """Инициализирует клиент Gemini API."""
        api_key = self.config["gemini_api_key"]
        if api_key == "ВАШ_GEMINI_API_КЛЮЧ_ЗДЕСЬ" or not api_key:
            logger.error("Gemini API key not set in config for GeminiPersonaMod!")
            self.gemini_client = None
            return False
        
        try:
            self.gemini_client = genai.Client(api_key=api_key)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self.gemini_client = None
            return False

    strings = {
        "name": "GeminiPersona",
        "api_key_h": "Ваш Google Gemini API ключ. Получите его на makersuite.google.com",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим GeminiPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим GeminiPersona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_api_key": "❌ Ошибка: Gemini API ключ не установлен или некорректен. Используйте `.config GeminiPersona` для настройки.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "HikkaPersona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "GeminiPersona",
        "api_key_h": "Ваш Google Gemini API ключ. Получите его на makersuite.google.com",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим GeminiPersona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим GeminiPersona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_api_key": "❌ Ошибка: Gemini API ключ не установлен или некорректен. Используйте `.config GeminiPersona` для настройки.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "HikkaPersona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Toggle Gemini persona for current chat."""
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
            if not self._init_gemini_client():
                return await utils.answer(m, self.strings("error_api_key"))

            self.active_chats[chat_id] = True
            await utils.answer(m, self.strings("ii_on").format(persona_name))

        self.db.set("GeminiPersonaMod", "active_chats", self.active_chats)

    # --- ВАЖНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Удалите @loader.listener(incoming=True, outgoing=False)
    # async def on_new_message(self, m: Message):
    async def on_new_message(self, event): # Теперь этот метод принимает объект event
        m = event.message # Получаем объект Message из event
    # --- КОНЕЦ ВАЖНОГО ИЗМЕНЕНИЯ ---

        if not m.is_private and not m.is_group:
            return

        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False):
            return  # Режим не активен в этом чате

        # Игнорируем сообщения от самого бота (вашего юзербота Hikka)
        # Получаем ID вашего аккаунта (владельца юзербота)
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        if m.text and m.text.startswith(".ii"):
            return  # Игнорируем саму команду .ii, чтобы избежать петли

        if not m.text:
            await utils.answer(m, self.strings("not_text"))
            return  # Отвечаем только на текстовые сообщения

        # Проверяем, инициализирован ли клиент Gemini
        if not self._init_gemini_client():
            await utils.answer(m, self.strings("error_api_key"))
            return

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]

        try:
            # Получаем историю чата для контекста
            history_messages = []
            # Используем messages.getHistory, т.к. iter_messages может быть долгим на больших чатах
            # и может быть не самым эффективным для 'последних X' сообщений.
            # Но для простоты и прямолинейности iter_messages тоже работает.
            # Если возникнут проблемы с производительностью, можно пересмотреть этот блок.
            async for msg in self.client.iter_messages(chat_id, limit=history_limit):
                if msg.text:
                    # Определяем имя отправителя
                    sender_name = persona_name if msg.sender_id == me.id else (msg.sender.first_name or msg.sender.username or f"Пользователь_{msg.sender_id}")
                    history_messages.append(f"{sender_name}: {msg.text}")
            
            # Переворачиваем историю, чтобы старые сообщения были в начале
            # Telethon.iter_messages возвращает сообщения от новых к старым.
            # Для контекста AI нам нужна хронологическая последовательность (старые -> новые).
            history_string = "\n".join(reversed(history_messages))

            prompt = (
                f"История диалога: ({history_string})\n\n"
                f"Думай что ты пользователь в телеграм с никнеймом {persona_name} отвечай как 18 летний человек "
                f"и пиши с маленькой буквы (упоминай никнейм и возраст только если спросят) и ты должен "
                f"коротко ответить на этот вопрос: ({m.text})"
            )

            # Случайная задержка
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Отправляем "думаю..." сообщение
            thinking_message = await utils.answer(m, self.strings("processing"))

            try:
                # Отправляем запрос в Gemini
                response = await self.gemini_client.models.generate_content(
                    model="gemini-2.5-flash-lite-preview-06-17",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_budget=0)  # Отключаем "мышление" для скорости
                    ),
                    timeout=30 # Таймаут на 30 секунд
                )
                response_text = response.text

                # Редактируем сообщение "думаю..." на ответ от AI
                # utils.answer автоматически редактирует переданное сообщение
                await utils.answer(thinking_message, response_text)

            except asyncio.TimeoutError:
                await utils.answer(thinking_message, self.strings("error_timeout"))
            except Exception as e:
                logger.error(f"Error getting response from Gemini: {e}", exc_info=True)
                await utils.answer(thinking_message, self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"Error in GeminiPersonaMod listener: {e}", exc_info=True)
            # Отправляем сообщение об ошибке, если что-то пошло не так на более высоком уровне
            await utils.answer(m, self.strings("error_processing").format(e))
