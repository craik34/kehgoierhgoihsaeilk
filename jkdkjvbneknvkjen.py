# meta developer: @mm_mods # Можно поменять на свой никнейм, или оставить так

__version__ = "1.0"

import asyncio
import random
import logging
from telethon.tl.patched import Message

from .. import loader, utils

# --- КОНФИГУРАЦИЯ API GOOGLE GEMINI ---
# !!! ВСТАВЬТЕ СЮДА ВАШ API КЛЮЧ GEMINI !!!
# Как получить: https://ai.google.dev/gemini-api/docs/get-started/python
# Просто перейдите по ссылке, нажмите "Get API Key" и следуйте инструкциям.
GEMINI_API_KEY = "AIzaSyCQijR-EI9Ird5YFPn1a2j3WQVH0g0qGPo" 
# Например: "AIzaSyC2k_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# --- НАСТРОЙКИ МОДЕЛИ И ПЕРСОНАЖА ---
# Используем стабильную модель. Модель 'gemini-2.5-flash-lite-preview-06-17' 
# может быть временной или ограниченной.
GEMINI_MODEL = "gemini-2.5-flash" 
# Ваш никнейм в Telegram для персоны бота
YOUR_TELEGRAM_NICKNAME = "крейк" 

# --- Инициализация библиотеки Google Gemini ---
# (Загружается при импорте модуля)
genai_client = None
try:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    # Проверка, что ключ установлен
    if not GEMINI_API_KEY or GEMINI_API_KEY == "ВАШ_API_КЛЮЧ_GEMINI_ЗДЕСЬ":
        logging.getLogger(__name__).error(
            "Gemini API key is not set. Please replace 'ВАШ_API_КЛЮЧ_GEMINI_ЗДЕСЬ' in the module code."
        )
    else:
        genai_client = genai
except ImportError:
    logging.getLogger(__name__).error(
        "Библиотека 'google-genai' не найдена. Установите ее: pip install google-genai"
    )
except Exception as e:
    logging.getLogger(__name__).error(f"Ошибка при инициализации Gemini API: {e}")

# --- СИСТЕМНАЯ ИНСТРУКЦИЯ ДЛЯ GEMINI ---
# Это основной "промпт" для AI, который определяет его поведение.
SYSTEM_INSTRUCTION = (
    f"Ты пользователь в Телеграм с никнеймом {YOUR_TELEGRAM_NICKNAME}. "
    "Тебе 18 лет. Отвечай как 18-летний человек. Пиши с маленькой буквы. "
    "Упоминай никнейм и возраст только если тебя спросят. Отвечай кратко."
)

@loader.tds
class GeminiResponderMod(loader.Module):
    """
    Интеллектуальный ответчик на базе Google Gemini AI.
    Команда .ii включает/выключает ответчик в чате.
    Бот будет отвечать на текстовые сообщения, имитируя человека.
    """
    strings = {
        "name": "GeminiResponder",
        "gemini_off": "🤖 <b>Gemini AI выключен.</b>",
        "gemini_on": "🟢 <b>Gemini AI включен.</b>",
        "no_api_key": "❌ Для работы модуля необходим Google Gemini API ключ. "
                      "Пожалуйста, вставьте его в код модуля 'gemini_responder.py'.",
    }

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "max_history_messages",
                30,
                lambda: "Максимальное количество сообщений для истории диалога.",
                validator=loader.validators.Integer(minimum=5, maximum=100),
            ),
            loader.ConfigValue(
                "min_response_delay",
                1.0,
                lambda: "Минимальная задержка перед ответом (в секундах).",
                validator=loader.validators.Float(minimum=0.5, maximum=10.0),
            ),
            loader.ConfigValue(
                "max_response_delay",
                4.0,
                lambda: "Максимальная задержка перед ответом (в секундах).",
                validator=loader.validators.Float(minimum=0.5, maximum=10.0),
            ),
            loader.ConfigValue(
                "max_output_tokens",
                80, # Делает ответы короткими
                lambda: "Максимальное количество токенов в ответе Gemini (для краткости).",
                validator=loader.validators.Integer(minimum=20, maximum=200),
            ),
        )
        self.enabled_chats = {} # Словарь для хранения состояния (вкл/выкл) для каждого чата

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        # Загружаем состояние enabled_chats из базы данных Hikka
        self.enabled_chats = self.db.get(self.strings["name"], "enabled_chats", {})

    def get_db_value(self, key, default):
        return self.db.get(self.strings["name"], key, default)

    def set_db_value(self, key, value):
        self.db.set(self.strings["name"], key, value)

    @loader.command(ru_doc="Включает/выключает Gemini AI ответчик в текущем чате.")
    async def iicmd(self, message: Message):
        chat_id = str(utils.get_chat_id(message))
        is_enabled = self.enabled_chats.get(chat_id, False)

        if is_enabled:
            self.enabled_chats[chat_id] = False
            await message.edit(self.strings("gemini_off"))
        else:
            if not genai_client or not GEMINI_API_KEY or GEMINI_API_KEY == "ВАШ_API_КЛЮЧ_GEMINI_ЗДЕСЬ":
                await message.edit(self.strings("no_api_key"))
                await asyncio.sleep(5) # Даем время прочитать сообщение об ошибке
                await message.delete() # Удаляем сообщение .ii
                return

            self.enabled_chats[chat_id] = True
            await message.edit(self.strings("gemini_on"))

        self.set_db_value("enabled_chats", self.enabled_chats)
        await asyncio.sleep(1) # Даем время пользователю увидеть сообщение
        await message.delete() # Удаляем команду .ii

    @loader.watcher(outgoing=False, func=lambda m: m.text and not m.media and not m.via_bot and m.peer_id)
    async def gemini_watcher(self, message: Message):
        """
        Отслеживает входящие текстовые сообщения, если Gemini AI включен для чата,
        и генерирует ответ.
        """
        chat_id = str(utils.get_chat_id(message))

        # Если Gemini AI не включен для этого чата, выходим
        if not self.enabled_chats.get(chat_id, False):
            return

        # Проверка наличия и инициализации клиента Gemini
        if not genai_client or not GEMINI_API_KEY or GEMINI_API_KEY == "ВАШ_API_КЛЮЧ_GEMINI_ЗДЕСЬ":
            logging.getLogger(__name__).warning(
                f"Gemini AI включен для чата {chat_id}, но API ключ отсутствует или некорректен."
            )
            return

        # Имитация набора текста
        try:
            await message.client.send_read_acknowledge(message.chat_id, message)
            await message.client.send_message(message.chat_id, action="typing")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Не удалось имитировать набор текста: {e}")

        # Умная случайная задержка
        message_len = len(message.text) if message.text else 0
        
        # Базовая задержка + фактор длины сообщения, чтобы казалось, что бот "читает"
        base_delay_min = self.config["min_response_delay"]
        base_delay_max = self.config["max_response_delay"]
        len_factor_per_char = 0.02 # Добавляем 0.02 секунды за каждый символ
        
        target_delay = random.uniform(base_delay_min, base_delay_max) + message_len * len_factor_per_char
        
        # Ограничиваем задержку, чтобы она не была слишком короткой или слишком длинной
        final_delay = max(0.5, min(target_delay, 7.0)) # Например, от 0.5 до 7 секунд
        
        await asyncio.sleep(final_delay)

        try:
            # Получаем историю диалога
            history = []
            async for msg in self.client.iter_messages(
                message.chat_id, limit=self.config["max_history_messages"], reverse=True
            ): # reverse=True чтобы старые сообщения были первыми
                if msg.text and not msg.media and not msg.via_bot and not msg.out: # Только текстовые, не медиа, не боты, не свои
                    sender_name = "неизвестный"
                    if msg.sender:
                        sender_name = msg.sender.first_name or msg.sender.username or "неизвестный"
                    elif msg.sender_chat: # Для каналов/групп
                        sender_name = msg.sender_chat.title or "неизвестный"
                    history.append(f"{sender_name}: {msg.text}")
                elif msg.out and msg.text and not msg.media: # Свои исходящие сообщения
                    history.append(f"{YOUR_TELEGRAM_NICKNAME}: {msg.text}")
                
            # Формируем промпт для Gemini, включая историю и системную инструкцию
            # Последнее сообщение в истории - это текущее сообщение, на которое отвечаем
            dialog_history = "\n".join(history[:-1]) # Вся история, кроме последнего (текущего) сообщения
            current_message_text = message.text # Текст текущего сообщения

            full_prompt = (
                f"История диалога: (\n{dialog_history}\n)\n\n"
                f"{SYSTEM_INSTRUCTION}\n\n"
                f"Ты должен коротко ответить на этот вопрос: ({current_message_text})"
            )

            model = genai_client.GenerativeModel(GEMINI_MODEL)
            
            # Настройки генерации ответа
            generation_config = {
                "temperature": 0.9, # Креативность (0.0-1.0)
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": self.config["max_output_tokens"], # Краткость ответа
                "response_mime_type": "text/plain", # Гарантируем текстовый ответ
            }

            # Настройки безопасности (можно изменить, если необходимо более жесткую фильтрацию)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            response = await model.generate_content(
                contents=[full_prompt],
                safety_settings=safety_settings,
                generation_config=generation_config,
            )
            
            response_text = response.text.strip()
            
            if response_text:
                await message.reply(response_text)

        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка при работе с Gemini AI: {e}", exc_info=True)
            # await message.reply("Произошла ошибка при генерации ответа.") # Можно включить для отладки
