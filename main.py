import asyncio
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
        status_msg = await message.reply("⏳ Обработка медиафайлов...")
        try:
            for i in range(0, size := len(res), 10):
                group = []
                for item in res[i : i + 10]:
                    async with fetch_to_buffer_async(item[1]) as buffer:
                        if item[0] == "video":
                            async with get_video_info_from_buffer_async(buffer) as data:
                                if size == 1:
                                    await message.reply_video(**data)
                                    return
                                video = InputMediaVideo(media=data.pop("video"), **data)
                                group.append(video)
                        elif item[0] == "photo":
                            file = BufferedInputFile(buffer.read(), filename="img.jpg")
                            if size == 1:
                                await message.reply_photo(file)
                                return
                            group.append(InputMediaPhoto(media=file))
                await message.reply_media_group(group)
        except Exception:
            await message.reply("❌ Ошибка")
        finally:
            await status_msg.delete()


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
