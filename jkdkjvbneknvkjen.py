
import asyncio
import logging
import collections

from hikka import loader, utils
from telethon.tl.patched import Message

# Import Gemini API
import google.generativeai as genai
from google.generativeai import types

logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ ---
# Вставьте сюда свой API-ключ Gemini
# ОЧЕНЬ ВАЖНО: Замените "ВАШ_API_КЛЮЧ_GEMINI" на ваш реальный ключ в кавычках!
GEMINI_API_KEY = "AIzaSyBhXRfIJ6Z79HKHjQiyjo-FQTR65Cxslkc"

# Ваш никнейм, который будет эмулировать бот
MY_NICKNAME = "крейк"

# Модель Gemini
GEMINI_MODEL = "gemini-2.5-flash-lite-preview-06-17"

# Максимальное количество сообщений в истории диалога для Gemini
MAX_HISTORY_MESSAGES = 30
# ---------------------

@loader.tds
class GeminiAutoResponderMod(loader.Module):
    """
    Автоответчик на базе Google Gemini.
    Включается/выключается командой .ii
    Эмулирует пользователя с никнеймом 'крейк' и возрастом 18 лет.
    """

    def __init__(self):
        self.name = "Gemini Автоответчик"
        # self.db будет инициализирован Hikka автоматически

        # Словарь для хранения истории диалогов по chat_id
        # Используем collections.deque для автоматического ограничения истории
        self.histories = collections.defaultdict(
            lambda: collections.deque(maxlen=MAX_HISTORY_MESSAGES)
        )
        self.gemini_model = None

    async def client_ready(self):
        """
        Инициализация клиента Gemini при готовности Hikka.
        """
        # Hikka сама передает объект базы данных в self.db.
        # Нет необходимости вызывать self.get_db() или self.db = None в __init__.
        # Просто используем self.db

        if not GEMINI_API_KEY or GEMINI_API_KEY == "ВАШ_API_КЛЮЧ_GEMINI":
            logger.error("Gemini API Key is not set or is default. Gemini auto-responder will not work.")
            return

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
            logger.info(f"Gemini API initialized with model {GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            self.gemini_model = None # Ensure it's None if init fails

    async def _save_message_to_history(self, chat_id: int, sender_name: str, text: str):
        """Сохраняет сообщение в историю диалога."""
        self.histories[chat_id].append(f"{sender_name}: {text}")

    async def _get_formatted_history(self, chat_id: int) -> str:
        """Форматирует историю диалога для передачи в промпт."""
        return "\n".join(self.histories[chat_id])

    @loader.command("ii", outgoing=True)
    async def iicmd(self, message: Message):
        """
        .ii - Включает/выключает автоответчик Gemini.
        Команда удаляется после выполнения.
        """
        # Удаляем команду .ii сразу же
        await message.delete()

        # Получаем текущее состояние и переключаем его
        is_active = self.db.get("gemini_active", False)
        self.db.set("gemini_active", not is_active)

        status_text = "включен" if not is_active else "выключен"

        # Отправляем временное сообщение о статусе и удаляем его через 2 секунды
        status_message = await utils.answer_messages(message, f"🤖 Автоответчик Gemini {status_text}!")
        await asyncio.sleep(2)
        await status_message.delete()

    @loader.watcher(only_messages=True, outgoing=False)
    async def gemini_watcher(self, message: Message):
        """
        Наблюдатель для входящих текстовых сообщений.
        """
        # Проверяем, активен ли автоответчик
        if not self.db.get("gemini_active", False):
            return

        # Игнорируем нетекстовые сообщения (фото, видео, стикеры, гифки, опросы)
        if not message.text:
            return

        # Игнорируем свои же сообщения
        if message.out:
            return

        # Игнорируем сообщения, которые начинаются с префикса команд Hikka
        # (чтобы не обрабатывать другие команды как вопросы к Gemini)
        if message.text.startswith(self.get_prefix()):
            return

        if not self.gemini_model:
            logger.warning("Gemini model is not initialized. Cannot respond.")
            return

        # Получаем имя отправителя для истории
        sender_name = "Неизвестный"
        if message.sender:
            sender_name = message.sender.first_name or message.sender.username or "Неизвестный"

        # Сохраняем текущее сообщение в историю
        await self._save_message_to_history(message.chat_id, sender_name, message.text)

        # Формируем историю диалога для промпта
        formatted_history = await self._get_formatted_history(message.chat_id)

        # Формируем системную инструкцию (persona)
        # Отключена в generate_content для более явного управления через contents
        # system_instruction = (
        #     f"Думай что ты пользователь в телеграм с никнеймом {MY_NICKNAME} "
        #     "отвечай как 18 летний человек и пиши с маленькой буквы "
        #     "(упоминай никнейм и возраст только если спросят)."
        # )

        # Формируем основной контент для запроса
        user_question = message.text
        full_prompt_content = (
            f"(История диалога: {MAX_HISTORY_MESSAGES} последних сообщений из чата или личных сообщений то есть например там никнейм: и {MY_NICKNAME}: то есть я)\n\n"
            f"Думай что ты пользователь в телеграм с никнеймом {MY_NICKNAME} отвечай как 18 летний человек и пиши с маленькой буквы "
            f"(упоминай никнейм и возраст только если спросят) и ты должен коротко ответить на этот вопрос: {user_question}\n"
            f"История диалога: \n{formatted_history}" # Помещаем историю в конец, как в вашем примере промпта
        )

        try:
            # Отправляем запрос в Gemini API
            # Если thinking_budget=0 вызывает ошибку, удалите эту строку или закомментируйте
            response = await asyncio.to_thread( # Используем asyncio.to_thread для блокирующих вызовов
                self.gemini_model.generate_content,
                contents=full_prompt_content,
                generation_config=types.GenerationConfig(
                    temperature=0.7, # Температура от 0 до 1, 0 - более предсказуемый, 1 - более креативный
                ),
                safety_settings=[ # Настройки безопасности
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
                #thinking_config=types.ThinkingConfig(thinking_budget=0) # Отключаем "мышление" для более быстрых ответов (может быть несовместимо с lite-preview)
            )

            generated_text = response.text

            # Сохраняем ответ Gemini в историю
            await self._save_message_to_history(message.chat_id, MY_NICKNAME, generated_text)

            # Отвечаем на сообщение пользователя
            await utils.answer_messages(message, generated_text)

        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
            # Если произошла ошибка API, можно опционально ответить пользователю
            # await utils.answer_messages(message, "Произошла ошибка при получении ответа от Gemini.")