import asyncio
import logging
import sys
from aiogram import F
from aiogram.types import Message
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from datetime import datetime
from aiogram.types import FSInputFile, InputMediaPhoto, InputMediaVideo
from utils import fetch_cobalt_links, fetch_and_save, calculate_video_params


# Bot token can be obtained via https://t.me/BotFather
TOKEN = "8151251504:AAGelzy_QixoiBsEfGwRmo6Bawup2ADUrLo"


dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user = message.from_user
    await message.answer(f"Hello, {html.bold(user.full_name if user else 'Guest')}!")


@dp.message(F.entities.extract(F.type == "url"))
async def echo_handler(message: Message) -> None:
    urls = [
        message.text[entity.offset : entity.offset + entity.length]
        for entity in message.entities or []
        if entity.type == "url" and message.text
    ]

    res = [item for url in urls if (el := await fetch_cobalt_links(url)) for item in el]

    if res:
        if len(res) == 1:
            for url in res:
                # await message.answer(f"• Ссылка: {url[0]}\n  Описание: {url[1]}")
                direct_link = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                await fetch_and_save(url[1], direct_link)
                if url[0] == "video":
                    params = calculate_video_params(direct_link)
                    await message.answer_video(**params)
                elif url[0] == "photo":
                    await message.answer_photo(FSInputFile(direct_link))
        elif len(res) > 1:
            for i in range(0, len(res), 10):
                batch = res[i : i + 10]
                media_group = []
                for item in batch:
                    direct_link = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                    await fetch_and_save(item[1], direct_link)
                    if item[0] == "video":
                        params = calculate_video_params(direct_link)
                        params["media"] = params.pop("video")
                        media_group.append(InputMediaVideo(**params))
                    elif item[0] == "photo":
                        media_group.append(
                            InputMediaPhoto(media=FSInputFile(direct_link))
                        )
                await message.reply_media_group(media_group)

    else:
        await message.answer("❌ Ссылки не найдены!")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
