# meta developer: @modwini

import asyncio
import random
import logging
from hikka import loader, utils
from telethon import events
from telethon.tl.patched import Message

# Импорт библиотеки g4f
import g4f

# Опционально: раскомментируйте для включения отладочного логирования g4f
# g4f.debug.logging = True
# g4f.check_version = False # Отключить автоматическую проверку версии g4f

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMod(loader.Module): # Название класса изменено для ясности
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны
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
                "ai_model",
                "gpt-4", # По умолчанию используем 'gpt-4' как запрошено
                lambda: self.strings("ai_model_h"),
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "ai_timeout",
                45, # Увеличиваем таймаут, так как бесплатные API могут быть медленными
                lambda: self.strings("ai_timeout_h"),
                validator=loader.validators.Integer(minimum=10, maximum=120),
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
            events.NewMessage(incoming=True, outgoing=False) # Слушаем только чужие сообщения
        )

    strings = {
        "name": "GPT4Persona", # Обновленное название модуля
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_model_h": "Модель AI для использования (например, 'gpt-4', 'gpt-3.5-turbo', 'default'). Убедитесь, что g4f поддерживает ее.",
        "ai_timeout_h": "Таймаут для ответа AI в секундах.",
        "ii_on": "🎭 Режим GPT4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим GPT4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "GPT4Persona отвечает только на текстовые сообщения.",
        "g4f_not_working": "❌ G4F Error: Не удалось получить ответ от AI. Возможно, нет рабочих провайдеров для выбранной модели ({}) или есть проблемы с доступом к free-API. Попробуйте другую модель или позже.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = { # Русский перевод строк
        "name": "GPT4Persona",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк')",
        "history_limit_h": "Количество последних сообщений для контекста (от 5 до 100).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ai_model_h": "Модель AI для использования (например, 'gpt-4', 'gpt-3.5-turbo', 'default'). Убедитесь, что g4f поддерживает ее.",
        "ai_timeout_h": "Таймаут для ответа AI в секундах.",
        "ii_on": "🎭 Режим GPT4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим GPT4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "GPT4Persona отвечает только на текстовые сообщения.",
        "g4f_not_working": "❌ G4F Error: Не удалось получить ответ от AI. Возможно, нет рабочих провайдеров для выбранной модели ({}) или есть проблемы с доступом к free-API. Попробуйте другую модель или позже.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Включает/выключает режим AI-персоны для текущего чата."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]
        
        # Определяем новое состояние
        is_active_now = not self.active_chats.get(chat_id, False)

        # Обновляем и сохраняем состояние
        self.active_chats[chat_id] = is_active_now
        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

        # Редактируем сообщение с командой, чтобы показать, что оно "удалено",
        # затем удаляем его полностью, чтобы избежать MessageIdInvalidError.
        try:
            await m.edit(self.strings("ii_deleted"))
            await asyncio.sleep(1) # Короткая задержка, чтобы пользователь увидел сообщение
            await m.delete()
        except Exception as e:
            logger.warning(f"Не удалось отредактировать/удалить сообщение команды: {e}")
            # Если редактирование/удаление не удалось, просто продолжаем отправлять статусное сообщение

        # Отправляем статусное сообщение как новое сообщение в чат
        status_message = self.strings("ii_on").format(persona_name) if is_active_now else self.strings("ii_off")
        await self.client.send_message(chat_id, status_message)


    async def on_new_message(self, event):
        m = event.message # Получаем объект Message из event

        # Игнорируем сообщения не из приватных чатов или групп
        if not m.is_private and not m.is_group:
            return

        chat_id = utils.get_chat_id(m)
        # Если режим не активен в этом чате, выходим
        if not self.active_chats.get(chat_id, False):
            return

        # Игнорируем сообщения от самого юзербота (владельца)
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        # Игнорируем саму команду .ii, чтобы избежать бесконечного цикла
        if m.text and m.text.lower().startswith(".ii"):
            return

        # Отвечаем только на текстовые сообщения
        if not m.text:
            await m.reply(self.strings("not_text"))
            return

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        ai_model = self.config["ai_model"]
        ai_timeout = self.config["ai_timeout"]

        try:
            # Получаем историю чата для контекста
            history_messages = []
            # Используем iter_messages для получения сообщений из чата
            async for msg_hist in self.client.iter_messages(chat_id, limit=history_limit):
                if msg_hist.text:
                    sender = await msg_hist.get_sender() # Получаем информацию об отправителе
                    # Определяем имя отправителя для истории
                    sender_name = persona_name if sender and sender.id == me.id else (sender.first_name or sender.username or f"Пользователь_{msg_hist.sender_id}")
                    history_messages.append(f"{sender_name}: {msg_hist.text}")
            
            # Переворачиваем историю, чтобы старые сообщения были в начале (хронологический порядок)
            history_string = "\n".join(reversed(history_messages))

            # Формируем промпт для AI с учетом persona и истории диалога
            prompt_content = (
                f"Ты — дружелюбный пользователь Telegram с никнеймом {persona_name}. "
                f"Твой возраст — 18 лет, и ты общаешься с другими пользователями. "
                f"Отвечай кратко и используй строчные буквы, если это уместно для непринужденного общения. "
                f"Упоминай свой никнейм или возраст, только если тебя об этом прямо спросят. "
                f"Вот история диалога для контекста:\n\n{history_string}\n\n"
                f"Теперь ответь на последнее сообщение: {m.text}"
            )

            # Случайная задержка перед обработкой и отправкой ответа, чтобы имитировать "думающего" человека
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Отправляем сообщение "думаю..." и сохраняем его ссылку, чтобы потом отредактировать
            thinking_message = await m.reply(self.strings("processing"))

            try:
                # Подготавливаем список сообщений для g4f.ChatCompletion.create
                # g4f ожидает список словарей с 'role' и 'content'
                g4f_messages = [{"role": "user", "content": prompt_content}]

                # Выполняем вызов g4f API
                full_response_text = ""
                response_generator = g4f.ChatCompletion.create(
                    model=ai_model, # Используем модель AI, указанную в конфигурации (например, 'gpt-4')
                    messages=g4f_messages,
                    stream=True, # Включаем потоковую передачу для лучшего пользовательского опыта
                    timeout=ai_timeout, # Используем таймаут из конфигурации
                )

                # Потоково отправляем ответ обратно в Telegram, редактируя сообщение "думаю..."
                last_edited_text = ""
                # Обрабатываем каждый фрагмент ответа
                async for message_chunk in response_generator:
                    if message_chunk and message_chunk != "[DONE]": # Игнорируем пустые фрагменты и сигнал [DONE]
                        full_response_text += message_chunk
                        # Редактируем сообщение периодически для отображения прогресса
                        # (например, каждые 50 символов или если текст очень короткий)
                        if len(full_response_text) - len(last_edited_text) > 50 or len(full_response_text) < 20: 
                            try:
                                await thinking_message.edit(full_response_text)
                                last_edited_text = full_response_text
                            except Exception as edit_e:
                                logger.warning(f"Ошибка при редактировании сообщения во время стриминга: {edit_e}")
                                # Если редактирование не удалось, продолжаем накапливать текст
                
                # Проверяем, получили ли мы хоть какой-то ответ
                if not full_response_text.strip():
                    raise ValueError(self.strings("g4f_not_working").format(ai_model))

                # Финальное редактирование сообщения с полным ответом
                await thinking_message.edit(full_response_text)

            except asyncio.TimeoutError:
                # Обработка таймаута
                await thinking_message.edit(self.strings("error_timeout"))
            except Exception as e:
                # Обработка ошибок, специфичных для g4f или общих
                logger.error(f"Ошибка при получении ответа от g4f: {e}", exc_info=True)
                if "Model not found" in str(e) or "No provider" in str(e) or "Rate limit" in str(e) or "Failed to connect" in str(e):
                    # Более информативное сообщение, если проблема с провайдерами g4f
                    error_message_to_send = self.strings("g4f_not_working").format(ai_model)
                else:
                    error_message_to_send = self.strings("error_processing").format(e)
                await thinking_message.edit(error_message_to_send)

        except Exception as e:
            # Обработка ошибок, произошедших вне блока вызова g4f (например, при получении истории)
            logger.error(f"Ошибка в слушателе Gpt4PersonaMod (внешний блок): {e}", exc_info=True)
            try:
                await m.reply(self.strings("error_processing").format(e))
            except Exception as reply_e:
                logger.error(f"Не удалось отправить ответ с ошибкой: {reply_e}", exc_info=True)
