import asyncio
import logging

from aiogram import F
from aiogram.types import Message
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

from aiogram.types import InputMediaPhoto, InputMediaVideo
from utils import (
    fetch_cobalt_links,
    get_video_info_from_buffer_async,
    fetch_to_buffer_async,
)

from aiogram.types import BufferedInputFile

# Bot token can be obtained via https://t.me/BotFather
TOKEN = " "


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
        answer = await message.reply("есть результаты, пробую скачать")
        try:
            if len(res) == 1:
                url = res[0]
                async with fetch_to_buffer_async(url[1]) as buffer:
                    if url[0] == "video":
                        async with get_video_info_from_buffer_async(buffer) as params:
                            await message.reply_video(**params)
                    elif url[0] == "photo":
                        await message.reply_photo(
                            BufferedInputFile(buffer.read(), filename="photo.jpg")
                        )

            elif len(res) > 1:
                for i in range(0, len(res), 10):
                    batch = res[i : i + 10]
                    media_group = []
                    for item in batch:
                        async with fetch_to_buffer_async(item[1]) as buffer:
                            if item[0] == "video":
                                async with get_video_info_from_buffer_async(
                                    buffer
                                ) as params:
                                    media_group.append(
                                        InputMediaVideo(
                                            media=params["video"],
                                            duration=params["duration"],
                                            width=params["width"],
                                            height=params["height"],
                                            thumbnail=params["thumbnail"],
                                        )
                                    )
                            elif item[0] == "photo":
                                media_group.append(
                                    InputMediaPhoto(
                                        media=BufferedInputFile(
                                            buffer.read(), filename="photo.jpg"
                                        )
                                    )
                                )
                    if media_group:
                        await message.reply_media_group(media_group)
        except Exception:
            await message.reply("что-то пошло не так")
        finally:
            await answer.delete()


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
