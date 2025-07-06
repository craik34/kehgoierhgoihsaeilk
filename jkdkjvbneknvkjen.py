# meta developer: @modwini

from .. import loader
from asyncio import sleep
import logging
from telethon import events
from telethon.tl.patched import Message
import g4f
import random

logger = logging.getLogger(__name__)

# Игнорируем проверку версии g4f и включаем логирование для отладки
g4f.debug.logging = True
g4f.check_version = False

@loader.tds
class Gpt4PersonaMod(loader.Module):
    """
    Модуль для Hikka, который позволяет пользователю отвечать в чате от имени AI-персоны "Крейк"
    с использованием GPT4Free.
    """

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "g4f_model",
                "gpt-3.5-turbo",  # Используем gpt-3.5-turbo по умолчанию
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
        "g4f_model_h": "Модель GPT4Free для использования (например, 'gpt-3.5-turbo', 'gpt-4').",
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
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    strings_ru = {
        "name": "Gpt4Persona",
        "g4f_model_h": "Модель GPT4Free для использования (например, 'gpt-3.5-turbo', 'gpt-4').",
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
        "_cmd_doc_ii": "Включает/выключает режим ответов от имени AI-персоны в текущем чате."
    }

    @loader.command("ii")
    async def iicmd(self, m: Message):
        """Toggle Gpt4 persona for current chat."""
        chat_id = utils.get_chat_id(m)
        persona_name = self.config["persona_name"]

        try:
            # Сначала удаляем сообщение с командой
            await m.delete()
            # Отправляем подтверждение об удалении
            # Это сообщение будет отправлено, а не отредактировано, чтобы избежать MessageIdInvalidError
            await utils.answer(m, self.strings("ii_deleted"))
        except Exception as e:
            logger.error(f"Error deleting command message or sending confirmation: {e}")
            # Если не удалось удалить, просто продолжаем
            pass

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

        me = await self.client.get_me()
        if m.sender_id == me.id:
            return # Игнорируем сообщения от самого бота (вашего юзербота Hikka)

        if m.text and m.text.startswith(".ii"):
            return # Игнорируем саму команду .ii, чтобы избежать петли

        if not m.text:
            # Не отвечаем на нетекстовые сообщения, но и не спамим "not_text" в чат.
            # Если это было бы reply, то можно было бы ответить на него.
            # Но для автоматического ответа, лучше просто проигнорировать.
            return

        persona_name = self.config["persona_name"]
        history_limit = self.config["history_limit"]
        min_delay = self.config["min_delay"]
        max_delay = self.config["max_delay"]
        g4f_model = self.config["g4f_model"]

        # Случайная задержка перед началом обработки
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

        # Отправляем "думаю..." сообщение
        thinking_message = await utils.answer(m, self.strings("processing"))

        try:
            # Получаем историю чата для контекста
            history_messages = []
            try:
                # Используем limit+1, чтобы гарантировать получение сообщения, на которое отвечаем
                # Игнорируем последнее сообщение, так как оно уже обрабатывается как current_message
                async for historic_msg in self.client.iter_messages(chat_id, limit=history_limit):
                    # Проверяем, что historic_msg.text не None перед использованием
                    if historic_msg.text and historic_msg.id != m.id:
                        sender_name = persona_name if historic_msg.sender_id == me.id else (historic_msg.sender.first_name or historic_msg.sender.username or f"Пользователь_{historic_msg.sender_id}")
                        history_messages.append(f"{sender_name}: {historic_msg.text}")
            except Exception as e:
                logger.warning(f"Failed to fetch chat history: {e}. Proceeding without full history.", exc_info=True)
                # Если историю не удалось получить, то history_messages останется пустым,
                # и промт будет сформирован без истории.

            # Переворачиваем историю, чтобы старые сообщения были в начале
            history_messages.reverse()
            history_string = "\n".join(history_messages)

            # Формируем промт с учетом персоны и стиля ответа
            prompt_parts = []
            if history_string:
                prompt_parts.append(f"История диалога:\n{history_string}")
            
            prompt_parts.append(
                f"Ты — пользователь телеграма с никнеймом '{persona_name}'. "
                f"Тебе 18 лет, и ты отвечаешь на сообщения, начиная предложение с маленькой буквы (если это не имя собственное). "
                f"Не упоминай свой никнейм или возраст, если тебя об этом прямо не спросят. "
                f"Отвечай коротко и по существу на следующее сообщение:\n"
                f"[{m.sender.first_name or m.sender.username or 'Собеседник'}]: {m.text}"
            )
            
            full_prompt = "\n\n".join(prompt_parts)

            # Отправляем запрос в GPT4Free
            response = g4f.ChatCompletion.create(
                model=g4f_model,
                messages=[{"role": "user", "content": full_prompt}],
                stream=False, # Не используем стриминг для простоты, так как редактируем одно сообщение
                timeout=30 # Таймаут на 30 секунд
            )
            
            response_text = response.strip() # Удаляем лишние пробелы

            # Редактируем сообщение "думаю..." на ответ от AI
            await utils.answer(thinking_message, response_text)

        except g4f.errors.ModelNotSupportedError as e:
            logger.error(f"G4F Model not supported: {e}", exc_info=True)
            await utils.answer(thinking_message, f"❌ Ошибка: Выбранная модель `{g4f_model}` не поддерживается или не найдена. Пожалуйста, проверьте `.config Gpt4Persona`.")
        except asyncio.TimeoutError:
            await utils.answer(thinking_message, self.strings("error_timeout"))
        except Exception as e:
            logger.error(f"Error getting response from Gpt4: {e}", exc_info=True)
            await utils.answer(thinking_message, self.strings("error_processing").format(e))

# rap module (без изменений, т.к. не связан с AI)
@loader.tds
class rap(loader.Module):
    strings = {"name": "Реп оксимирона"}

    @loader.owner
    async def rapcmd(self, message):
        for _ in range(1):
            for rap_word in ["Говно", "залупа", "пенис", "хер", "давалка", "хуй", "блядина",
"Головка", "шлюха", "жопа", "член", "еблан", "петух…", "Мудила",
"Рукоблуд", "ссанина", "очко", "блядун", "вагина",
"Сука", "ебланище", "влагалище", "пердун", "дрочила",
"Пидор", "пизда", "туз", "малафья",
"Гомик", "мудила", "пилотка", "манда"
"Анус", "вагина", "путана", "педрила",
"Шалава", "хуило", "мошонка", "елда…",
"Раунд!"]:
                await message.edit(rap_word)
                await sleep(0.3)

# DemotivatorsMod (без изменений, т.к. не связан с AI)
from PIL import Image, ImageDraw, ImageOps, ImageFont
from textwrap import wrap
import io
import requests

logger = logging.getLogger(__name__)

@loader.tds
class DeMoTiVaToRsMod(loader.Module):
    """Демотиваторы на картинки от @SomeScripts by @DneZyeK"""
    strings = {
        "name": "SuperDemotivator"
    }

    async def client_ready(self, client, db):
        self.client = client
    
    @loader.owner
    async def demoticmd(self, message):
        """текст + фото или ответ на фото
           не мнёт фотки"""
        await cmds(message, 0)
        
    async def demotcmd(self, message):
        """текст + фото или ответ на фото
           мнёт фотки"""
        await cmds(message, 1)
        
async def cmds(message, type):
    event, is_reply = await check_media(message)
    if not event:
        await message.edit("<b>Ответ командой на картинку!</b>")
        return
    text = utils.get_args_raw(message)
    
    if not text:
        text = random.choice(tttxxx)
        
    await message.edit("<b>Демотивирую...</b>")
    bytes_image = await event.download_media(bytes)
    demotivator = await demotion(font_bytes, bytes_image, text, type)
    if is_reply:
        await message.delete()
        return await event.reply(file=demotivator)
        
    else:
        return await event.edit(file=demotivator, text="")
    
async def check_media(message):
    reply = await message.get_reply_message()
    is_reply = True
    if not reply:
        reply = message
        is_reply = False
    if not reply.file:
        return False, ...
    mime = reply.file.mime_type.split("/")[0].lower()
    if mime != "image":
        return False, ...
    return reply, is_reply
    
async def textwrap(text, length=50, splitter = "\n\n"):
    out = []
    lines = text.rsplit(splitter, 1)
    for text in lines:
        txt = []
        parts = text.split("\n")
        for part in parts:
            part = "\n".join(wrap(part, length))
            txt.append(part)
        text = "\n".join(txt)
        out.append(text)
    return out

async def draw_main(
            bytes_image,
            type,
            frame_width_1 = 5,
            frame_fill_1 = (0, 0, 0),
            frame_width_2 = 3,
            frame_fill_2 = (255, 255, 255),
            expand_proc = 10,
            main_fill = (0, 0, 0)
            ):
                
    main_ = Image.open(io.BytesIO(bytes_image))
    main = Image.new("RGB", main_.size, "black")
    main.paste(main_, (0, 0))
    if type == 1:
        main = main.resize((700, 550))
    main = ImageOps.expand(main, frame_width_1, frame_fill_1)
    main = ImageOps.expand(main, frame_width_2, frame_fill_2)
    w, h = main.size
    h_up = expand_proc*(h//100)
    im = Image.new("RGB", (w+(h_up*2), h+h_up), main_fill)
    im.paste(main, (h_up, h_up))
    return im

async def _draw_text(
            text,
            font_bytes,
            font_size,
            font_add = 20,
            main_fill = (0, 0, 0),
            text_fill = (255, 255, 255),
            text_align = "center"
            ):
                
    font = ImageFont.truetype(io.BytesIO(font_bytes), font_size)
    w_txt, h_txt = ImageDraw.Draw(Image.new("RGB", (1, 1))).multiline_textsize(text=text, font=font)
    txt = Image.new("RGB", (w_txt, h_txt+font_add), main_fill)
    ImageDraw.Draw(txt).text((0, 0), text=text, font=font, fill=text_fill, align=text_align)
    return txt
    
async def text_joiner(text_img_1, text_img_2, main_fill = (0, 0, 0)):
    w_txt_1, h_txt_1 = text_img_1.size
    w_txt_2, h_txt_2 = text_img_2.size
    w = max(w_txt_1, w_txt_2)
    h = h_txt_1 + h_txt_2
    text = Image.new("RGB", (w, h), main_fill)
    text.paste(text_img_1, ((w-w_txt_1)//2, 0))
    text.paste(text_img_2, ((w-w_txt_2)//2, h_txt_1))
    return text
    
async def draw_text(text, font_bytes, font_size):
    text = await textwrap(text)
    if len(text) == 1:
        text = await _draw_text(text[0], font_bytes, font_size[0] )
    else:
        text_img_1 = await _draw_text(text[ 0], font_bytes, font_size[0])
        text_img_2 = await _draw_text(text[-1], font_bytes, font_size[1])
        text = await text_joiner(text_img_1, text_img_2)
    return text
    
async def text_finaller(text, main, expand_width_proc = 25, main_fill = (0, 0, 0)):
    x = min(main.size)
    w_txt, h_txt = text.size
    w_proc = expand_width_proc*(w_txt//100)
    h_proc = expand_width_proc*(h_txt//100)
    back = Image.new("RGB", (w_txt+(w_proc*2), h_txt+(h_proc*2)), main_fill)
    back.paste(text, (w_proc, h_proc))
    back.thumbnail((x, x))
    return back
    
    
async def joiner(text_img, main_img, format_save="JPEG"):
    w_im, h_im = main_img.size
    w_txt, h_txt = text_img.size
    text_img.thumbnail((min(w_im, h_im), min(w_im, h_im)))
    w_txt, h_txt = text_img.size
    main_img = main_img.crop((0, 0, w_im, h_im+h_txt))
    main_img.paste(text_img, ((w_im-w_txt)//2, h_im))
    output = io.BytesIO()
    main_img.save(output, format_save)
    output.seek(0)
    return output.getvalue()
    
async def demotion(font_bytes, bytes_image, text, type):
    main = await draw_main(bytes_image, type)
    font_size = [20*(min(main.size)//100), 15*(min(main.size)//100)]
    text = await draw_text(text, font_bytes, font_size)
    text = await text_finaller(text, main)
    output = await joiner(text, main)
    return output

tttxxx = ['А че', 'заставляет задуматься', 'Жалко пацана', 'ты че сука??', 'ААХАХАХАХХАХА\n\nААХАХААХАХА', 'ГИГАНТ МЫСЛИ\n\nотец русской демократии', 'Он', 'ЧТО БЛЯТЬ?', 'охуенная тема', 'ВОТ ОНИ\n\nтипичные комедиклабовские шутки', 'НУ НЕ БЛЯДИНА?', 'Узнали?', 'Согласны?', 'Вот это мужик', 'ЕГО ИДЕИ\n\nбудут актуальны всегда', '\n\nПРИ СТАЛИНЕ ОН БЫ СИДЕЛ', 'о вадим', '2 месяца на дваче\n\nи это, блядь, нихуя не смешно', 'Что дальше?\n\nЧайник с функцией жопа?', '\n\nИ нахуя мне эта информация?', 'Верхний текст', 'нижний текст', 'Показалось', 'Суды при анкапе', 'Хуйло с района\n\n\n\nтакая шелупонь с одной тычки ляжет', 'Брух', 'Расскажи им\n\nкак ты устал в офисе', 'Окурок блять\n\nесть 2 рубля?', 'Аниме ставшее легендой', 'СМИРИСЬ\n\n\n\nты никогда не станешь настолько же крутым', 'а ведь это идея', '\n\nЕсли не лайкнешь у тебя нет сердца', 'Вместо тысячи слов', 'ШАХ И МАТ!!!', 'Самый большой член в мире\n\nУ этой девушки', 'Немного\n\nперфекционизма', 'кто', '\n\nэта сука уводит чужих мужей', 'Кто он???', '\n\nВы тоже хотели насрать туда в детстве?', '\n\nВся суть современного общества\n\nв одном фото', 'Он обязательно выживет!', '\n\nВы тоже хотите подрочить ему?', '\n\nИ вот этой хуйне поклоняются русские?', 'Вот она суть\n\n\n\nчеловеческого общества в одной картинке', 'Вы думали это рофл?\n\nНет это жопа', '\n\nПри сталине такой хуйни не было\n\nА у вас было?', 'Он грыз провода', 'Назло старухам\n\nна радость онанистам', 'Где-то в Челябинске', 'Агитация за Порошенко', 'ИДЕАЛЬНО', 'Грыз?', 'Ну давай расскажи им\n\nкакая у тебя тяжелая работа', '\n\nЖелаю в каждом доме такого гостя', 'Шкура на вырост', 'НИКОГДА\n\nне сдавайся', 'Оппа гангнам стайл\n\nуууу сэкси лейди оп оп', 'Они сделали это\n\nсукины дети, они справились', 'Эта сука\n\nхочет денег', 'Это говно, а ты?', '\n\nВот она нынешняя молодежь', 'Погладь кота\n\nпогладь кота сука', 'Я обязательно выживу', '\n\nВот она, настоящая мужская дружба\n\nбез политики и лицимерия', '\n\nОБИДНО ЧТО Я ЖИВУ В СТРАНЕ\n\nгде гантели стоят в 20 раз дороже чем бутылка водки', 'Царь, просто царь', '\n\nНахуй вы это в учебники вставили?\n\nИ ещё ебаную контрольную устроили', '\n\nЭТО НАСТОЯЩАЯ КРАСОТА\n\nа не ваши голые бляди', '\n\nТема раскрыта ПОЛНОСТЬЮ', '\n\nРОССИЯ, КОТОРУЮ МЫ ПОТЕРЯЛИ', 'ЭТО - Я\n\nПОДУМАЙ МОЖЕТ ЭТО ТЫ', 'почему\n\nчто почему', 'КУПИТЬ БЫ ДЖЫП\n\nБЛЯТЬ ДА НАХУЙ НАДО', '\n\n\n\nмы не продаём бомбастер лицам старше 12 лет', 'МРАЗЬ', 'Правильная аэрография', 'Вот она русская\n\nСМЕКАЛОЧКА', 'Он взял рехстаг!\n\nА чего добился ты?', 'На аватарку', 'Фотошоп по-деревенски', 'Инструкция в самолете', 'Цирк дю Солей', 'Вкус детства\n\nшколоте не понять', 'Вот оно - СЧАСТЬЕ', 'Он за тебя воевал\n\nа ты даже не знаешь его имени', 'Зато не за компьютером', '\n\nНе трогай это на новый год', 'Мой первый рисунок\n\nмочой на снегу', '\n\nМайские праздники на даче', 'Ваш пиздюк?', 'Тест драйв подгузников', 'Не понимаю\n\nкак это вообще выросло?', 'Супермен в СССР', 'Единственный\n\nкто тебе рад', 'Макдональдс отдыхает', 'Ну че\n\n как дела на работе пацаны?', 'Вся суть отношений', 'Беларусы, спасибо!', '\n\nУ дверей узбекского военкомата', 'Вместо 1000 слов', 'Один вопрос\n\nнахуя?', 'Ответ на санкции\n\nЕВРОПЫ', 'ЦЫГАНСКИЕ ФОКУСЫ', 'Блять!\n\nда он гений!', '\n\nУкраина ищет новые источники газа', 'ВОТ ЭТО\n\nНАСТОЯЩИЕ КАЗАКИ а не ряженные', 'Нового года не будет\n\nСанта принял Ислам', '\n\nОн был против наркотиков\n\nа ты и дальше убивай себя', 'Всем похуй!\n\nВсем похуй!', 'БРАТЬЯ СЛАВЯНЕ\n\nпомните друг о друге', '\n\nОН ПРИДУМАЛ ГОВНО\n\nа ты даже не знаешь его имени', '\n\nкраткий курс истории нацболов', 'Эпоха ренессанса']
font_bytes = requests.get("https://raw.githubusercontent.com/KeyZenD/l/master/times.ttf").content

# DelmeMod (без изменений, т.к. не связан с AI)
@loader.tds
class DelmeMod(loader.Module):
    """Удаляет все сообщения"""
    strings = {'name': 'DelMe'}
    @loader.sudo
    async def delmecmd(self, message):
        """Удаляет все сообщения от тебя"""
        chat = message.chat
        if chat:
            args = utils.get_args_raw(message)
            if args != str(message.chat.id+message.sender_id):
                await message.edit(f"<b>Если ты точно хочешь это сделать, то напиши:</b>\n<code>.delme {message.chat.id+message.sender_id}</code>")
                return
            await delete(chat, message, True)
        else:
            await message.edit("<b>В лс не чищу!</b>")
    @loader.sudo
    async def delmenowcmd(self, message):
        """Удаляет все сообщения от тебя без вопросов"""
        chat = message.chat
        if chat:
            await delete(chat, message, False)
        else:
            await message.edit("<b>В лс не чищу!</b>")

async def delete(chat, message, now):
    if now:
        all = (await message.client.get_messages(chat, from_user="me")).total
        await message.edit(f"<b>{all} сообщений будет удалено!</b>")
    else: await message.delete()
    _ = not now
    async for msg in message.client.iter_messages(chat, from_user="me"):
        if _:
            await msg.delete()
        else:
            _ = "_"
    await message.delete() if now else "хули мусара хули мусара хули, едем так как ехали даже в хуй не дули"

# MSMod (без изменений, т.к. не связан с AI)
# @loader.tds # Этот декоратор не нужен, т.к. register уже вызывает класс
class MSMod(loader.Module):
    """Спаммер медиа(стикер/гиф/фото/видео/войс/видеовойс"""
    strings = {'name': 'МедиаСпам'}

    def __init__(self):
        self.name = self.strings['name']
        self._me = None
        self._ratelimit = []

    async def client_ready(self, client, db):
        self._db = db
        self._client = client
        self.me = await client.get_me()

    async def mediaspamcmd(self, message):
        """.mediaspam <количество> + реплай на медиа(стикер/гиф/фото/видео/войс/видеовойс)"""
        reply = await message.get_reply_message()
        if not reply:
            await message.edit("<code>.mediaspam <количество> + реплай на медиа(стикер/гиф/фото/видео/войс/видеовойс</code>")
            return
        if not reply.media:
            await message.edit("<code>.mediaspam <количество> + реплай на медиа(стикер/гиф/фото/видео/войс/видеовойс</code>")
            return
        media = reply.media
    
        args = utils.get_args(message)
        if not args:
            await message.edit("<code>.mediaspam <количество> + реплай на медиа(стикер/гиф/фото/видео/войс/видеовойс</code>")
            return
        count = args[0]
        count = count.strip()
        if not count.isdigit():
            await message.edit("<code>.mediaspam <количество> + реплай на медиа(стикер/гиф/фото/видео/войс/видеовойс</code>")
            return
        count = int(count)
        
        await message.delete()
        for _ in range(count):
            await message.client.send_file(message.to_id, media)
