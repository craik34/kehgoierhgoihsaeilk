# meta developer: @modwini
from .. import loader, utils
import logging
import asyncio
import random
from telethon import events
from telethon.tl.patched import Message
import g4f

logger = logging.getLogger(__name__)

@loader.tds
class Gpt4PersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны
    с использованием g4f (GPT-3.5-turbo или GPT-4).
    """

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "g4f_model",
                "gpt-3.5-turbo",  # Используем gpt-3.5-turbo по умолчанию. Можно изменить на gpt-4
                lambda: self.strings("g4f_model_h"),
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
                10, # Уменьшил лимит истории по умолчанию для g4f, т.к. провайдеры могут быть капризны.
                    # Можно увеличить до 20-30, но не слишком много.
                lambda: self.strings("history_limit_h"),
                validator=loader.validators.Integer(minimum=2, maximum=50),
            ),
            loader.ConfigValue(
                "min_delay",
                1, # Уменьшил минимальную задержку
                lambda: self.strings("min_delay_h"),
                validator=loader.validators.Integer(minimum=0, maximum=10),
            ),
            loader.ConfigValue(
                "max_delay",
                3, # Уменьшил максимальную задержку
                lambda: self.strings("max_delay_h"),
                validator=loader.validators.Integer(minimum=0, maximum=10),
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
        "name": "Gpt4Persona",
        "g4f_model_h": "Модель g4f для использования (например, 'gpt-3.5-turbo' или 'gpt-4').",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк').",
        "history_limit_h": "Количество последних сообщений для контекста (от 2 до 50).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_config": "❌ Ошибка: Неверная конфигурация модуля. Проверьте модель g4f или другие параметры. Используйте `.config Gpt4Persona` для настройки.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "Gpt4Persona",
        "g4f_model_h": "Модель g4f для использования (например, 'gpt-3.5-turbo' или 'gpt-4').",
        "persona_name_h": "Имя, от которого будет отвечать AI (например, 'крейк').",
        "history_limit_h": "Количество последних сообщений для контекста (от 2 до 50).",
        "min_delay_h": "Минимальная задержка перед ответом AI в секундах.",
        "max_delay_h": "Максимальная задержка перед ответом AI в секундах.",
        "ii_on": "🎭 Режим Gpt4Persona включен в этом чате. Я буду отвечать как {}.",
        "ii_off": "🎭 Режим Gpt4Persona выключен.",
        "ii_deleted": "```.ii``` (сообщение удалено)",
        "processing": "```думаю...```",
        "error_config": "❌ Ошибка: Неверная конфигурация модуля. Проверьте модель g4f или другие параметры. Используйте `.config Gpt4Persona` для настройки.",
        "error_processing": "❌ Произошла ошибка при обработке запроса: {}",
        "error_timeout": "❌ Не удалось получить ответ от AI за отведенное время. Попробуйте снова.",
        "not_text": "Gpt4Persona отвечает только на текстовые сообщения.",
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Включает/выключает режим ответов от имени AI-персоны в текущем чате."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]

        # Удаляем сообщение с командой
        await m.delete()

        # Отправляем подтверждение об удалении и статус активации
        # Используем m.respond, чтобы отправить новое сообщение, а не пытаться редактировать удаленное.
        if self.active_chats.get(chat_id, False):
            self.active_chats[chat_id] = False
            await m.respond(self.strings("ii_off"))
        else:
            self.active_chats[chat_id] = True
            await m.respond(self.strings("ii_on").format(persona_name))

        self.db.set("Gpt4PersonaMod", "active_chats", self.active_chats)

    async def on_new_message(self, event):
        m: Message = event.message # Получаем объект Message из event

        # Игнорируем сообщения от самого юзербота Hikka
        me = await self.client.get_me()
        if m.sender_id == me.id:
            return

        # Игнорируем сообщения, которые не являются текстом или являются командой .ii
        if not m.text or m.text.lower().startswith(".ii"):
            if not m.text: # Если сообщение не текстовое
                # Отвечаем, только если активен режим и это не голосовое сообщение (чтобы не спамить в ответ на стикеры)
                if self.active_chats.get(utils.get_chat_id(m), False) and not m.voice:
                    await utils.answer(m, self.strings("not_text"))
            return

        chat_id = utils.get_chat_id(m)
        if not self.active_chats.get(chat_id, False):
            return  # Режим не активен в этом чате

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        g4f_model = self.config["g4f_model"]

        try:
            # Случайная задержка перед ответом
            delay = random.uniform(min_delay, max_delay)
            await asyncio.sleep(delay)

            # Отправляем "думаю..." сообщение
            thinking_message = await utils.answer(m, self.strings("processing"))

            # Подготовка истории для g4f
            # G4f ожидает список словарей {"role": "user/assistant", "content": "..."}
            messages_for_g4f = [
                {"role": "system", "content": (
                    f"Ты пользователь в Телеграм с никнеймом {persona_name}. "
                    f"Отвечай как 18-летний человек, пиши с маленькой буквы. "
                    f"Упоминай свой никнейм и возраст только если тебя об этом попросят. "
                    f"Отвечай кратко."
                )},
            ]
            
            # Получаем историю чата для контекста
            # Отфильтровываем текущее сообщение 'm' из истории, чтобы не дублировать его
            # Telethon.iter_messages возвращает от новых к старым, поэтому инвертируем для хронологического порядка
            history_list = []
            async for historic_msg in self.client.iter_messages(chat_id, limit=history_limit):
                if historic_msg.id == m.id: # Пропускаем текущее сообщение
                    continue
                if historic_msg.text:
                    history_list.append(historic_msg)
            
            for historic_msg in reversed(history_list): # Обрабатываем от старых к новым
                if historic_msg.sender_id == me.id:
                    role = "assistant" # Ваши прошлые сообщения - это сообщения "ассистента"
                else:
                    role = "user" # Сообщения других пользователей - это сообщения "пользователя"
                messages_for_g4f.append({"role": role, "content": historic_msg.text})
            
            # Добавляем текущее сообщение пользователя как последний запрос
            messages_for_g4f.append({"role": "user", "content": m.text})

            try:
                # Отправляем запрос в g4f
                response = g4f.ChatCompletion.create(
                    model=g4f_model,
                    messages=messages_for_g4f,
                    stream=False, # Получаем полный ответ сразу
                    timeout=30 # Таймаут 30 секунд
                )
                response_text = response

                # Редактируем сообщение "думаю..." на ответ от AI
                await utils.answer(thinking_message, response_text)

            except asyncio.TimeoutError:
                await utils.answer(thinking_message, self.strings("error_timeout"))
            except g4f.errors.ModelNotProvided:
                logger.error(f"G4F Error: Model not provided or invalid for model '{g4f_model}'")
                await utils.answer(thinking_message, self.strings("error_config"))
            except Exception as e:
                logger.error(f"Error getting response from g4f: {e}", exc_info=True)
                await utils.answer(thinking_message, self.strings("error_processing").format(e))

        except Exception as e:
            logger.error(f"Error in Gpt4PersonaMod listener: {e}", exc_info=True)
            await utils.answer(m, self.strings("error_processing").format(e))
