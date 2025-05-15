import httpx
import aiofiles
from pathlib import Path
import asyncio
import aiohttp
from typing import List, Tuple, Optional


async def fetch_and_save(url: str, filename: str, max_size_mb: int = 50) -> None:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
    }

    MAX_SIZE_BYTES = max_size_mb * 1024 * 1024

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Проверка размера через HEAD
            head_response = await client.head(
                url, headers=HEADERS, follow_redirects=True
            )
            head_response.raise_for_status()

            content_length = head_response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_SIZE_BYTES:
                raise ValueError(f"File size exceeds limit ({max_size_mb} MB)")

            # Потоковая загрузка с контролем размера
            downloaded = 0
            async with client.stream(
                "GET", url, headers=HEADERS, follow_redirects=True
            ) as response:
                response.raise_for_status()

                # Создаем папку если не существует
                Path(filename).parent.mkdir(parents=True, exist_ok=True)

                async with aiofiles.open(filename, "wb") as file:
                    async for chunk in response.aiter_bytes():
                        await file.write(chunk)
                        downloaded += len(chunk)
                        if downloaded > MAX_SIZE_BYTES:
                            raise ValueError(
                                f"File size exceeded limit ({max_size_mb} MB)"
                            )

            # Файл успешно сохранен

        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            # Удаляем частично загруженный файл при ошибке
            if Path(filename).exists():
                Path(filename).unlink()
            raise ValueError(f"Download failed: {str(e)}") from e


def determine_media_type(filename: Optional[str]) -> str:
    """Определяет тип медиа по расширению файла"""
    if not filename:
        return "unknown"

    # Словарь соответствий расширений типам медиа
    extension_map = {
        # Видео
        "mp4": "video",
        "mov": "video",
        "avi": "video",
        "mkv": "video",
        "webm": "video",
        "flv": "video",
        # Аудио
        "mp3": "audio",
        "wav": "audio",
        "ogg": "audio",
        "m4a": "audio",
        "flac": "audio",
        "aac": "audio",
        # Изображения
        "jpg": "photo",
        "jpeg": "photo",
        "png": "photo",
        "gif": "gif",
        "webp": "photo",
        "bmp": "photo",
    }

    try:
        ext = filename.split(".")[-1].lower()
        return extension_map.get(ext, "unknown")
    except Exception:
        return "unknown"


async def fetch_cobalt_links(
    media_url: str,
    api_url: str = "http://localhost:9000/",
    timeout: int = 30,
) -> List[Tuple[str, str]]:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"url": media_url, "videoQuality": "720", "downloadMode": "auto"}

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout)
    ) as session:
        async with session.post(api_url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ValueError(f"API returned {response.status}: {error_text}")
            data = await response.json()
            if data["status"] in ("redirect", "tunnel"):
                media_type = determine_media_type(data["filename"])
                return [(media_type, data["url"])]
            elif data["status"] == "picker":
                return [(item["type"], item["url"]) for item in data["picker"]]
            elif data["status"] == "error":
                raise ValueError(f"Cobalt API error: {data['error']['code']}")
            raise ValueError(f"Unknown response status: {data['status']}")


def syncfunc():
    async def asyncfunc():
        print(await fetch_cobalt_links("https://www.instagram.com/p/DJrajw5JF22/"))

        # await fetch_and_save(
        #     url="http://localhost:9000/tunnel?id=rmBEYTo_u0ekU9oKxrdZG&exp=1747317723080&sig=W-IUa0xsltO8uxO5Ko_Y95sQ1GYeQvjiL0nux1jMTVw&sec=Yotyuahw-fPZKFLty_DYCW4K5zPFrIQq8ZhTbovqRd4&iv=kuaNnaff8WNtVtZjMOZvLA",
        #     filename="tiktok_kireev_voice_7504644103678741768.mp4",
        #     max_size_mb=100,  # Лимит 100 MB
        # )

    asyncio.run(asyncfunc())


syncfunc()
