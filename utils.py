import httpx
import aiofiles

import asyncio
import aiohttp
from typing import List, Tuple, Optional, Literal, Dict


from contextlib import asynccontextmanager
import io
import cv2
from aiogram.types import BufferedInputFile


@asynccontextmanager
async def fetch_to_buffer_async(url: str, max_size_mb: int = 50):
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
    }
    MAX_SIZE_BYTES = max_size_mb * 1024 * 1024
    buffer = io.BytesIO()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if head := await client.head(url, headers=HEADERS, follow_redirects=True):
                if int(head.headers.get("Content-Length", 0)) > MAX_SIZE_BYTES:
                    raise ValueError("Size limit exceeded")

            downloaded = 0
            async with client.stream(
                "GET", url, headers=HEADERS, follow_redirects=True
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    buffer.write(chunk)
                    if (downloaded := downloaded + len(chunk)) > MAX_SIZE_BYTES:
                        raise ValueError("Size limit exceeded")
            buffer.seek(0)
            yield buffer

    except Exception as e:
        raise ValueError(f"Download failed: {str(e)}") from e
    finally:
        buffer.close()


@asynccontextmanager
async def get_video_info_from_buffer_async(buffer: io.BytesIO):
    def sync_video_analysis(video_path: str):
        cap = cv2.VideoCapture(video_path)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = int(frame_count / fps) if fps > 0 else 0
            success, first_frame = cap.read()
            if not success:
                raise ValueError("Failed to read video frame")
            return duration, width, height, first_frame
        finally:
            cap.release()

    async with aiofiles.tempfile.NamedTemporaryFile("wb") as temp_file:
        await temp_file.write(buffer.read())
        buffer.seek(0)
        duration, width, height, frame = await asyncio.to_thread(
            sync_video_analysis, str(temp_file.name)
        )
        _, buffer_img = cv2.imencode(".jpg", frame)
        yield {
            "video": BufferedInputFile(buffer.read(), filename="video.mp4"),
            "duration": duration,
            "width": width,
            "height": height,
            "thumbnail": BufferedInputFile(
                buffer_img.tobytes(), filename="thumbnail.jpg"
            ),
        }


# async def fetch_and_save(url: str, filename: str, max_size_mb: int = 50) -> None:
#     HEADERS = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
#         "Accept": "*/*",
#         "Accept-Encoding": "gzip, deflate, br",
#     }

#     MAX_SIZE_BYTES = max_size_mb * 1024 * 1024

#     async with httpx.AsyncClient(timeout=30.0) as client:
#         try:
#             # Проверка размера через HEAD
#             head_response = await client.head(
#                 url, headers=HEADERS, follow_redirects=True
#             )
#             head_response.raise_for_status()

#             content_length = head_response.headers.get("Content-Length")
#             if content_length and int(content_length) > MAX_SIZE_BYTES:
#                 raise ValueError(f"File size exceeds limit ({max_size_mb} MB)")

#             # Потоковая загрузка с контролем размера
#             downloaded = 0
#             async with client.stream(
#                 "GET", url, headers=HEADERS, follow_redirects=True
#             ) as response:
#                 response.raise_for_status()

#                 # Создаем папку если не существует
#                 Path(filename).parent.mkdir(parents=True, exist_ok=True)

#                 async with aiofiles.open(filename, "wb") as file:
#                     async for chunk in response.aiter_bytes():
#                         await file.write(chunk)
#                         downloaded += len(chunk)
#                         if downloaded > MAX_SIZE_BYTES:
#                             raise ValueError(
#                                 f"File size exceeded limit ({max_size_mb} MB)"
#                             )

#             # Файл успешно сохранен

#         except httpx.HTTPStatusError as e:
#             raise ValueError(f"HTTP error: {e.response.status_code}") from e
#         except Exception as e:
#             # Удаляем частично загруженный файл при ошибке
#             if Path(filename).exists():
#                 Path(filename).unlink()
#             raise ValueError(f"Download failed: {str(e)}") from e


def determine_media_type(
    filename: Optional[str],
) -> Optional[Literal["video", "audio", "photo"]]:
    """Определяет тип медиафайла по его расширению."""
    if not filename:
        return None

    extension_map: Dict[str, Literal["video", "audio", "photo"]] = {
        "mp4": "video",
        "mov": "video",
        "avi": "video",
        "mkv": "video",
        "webm": "video",
        "flv": "video",
        "gif": "video",
        "mp3": "audio",
        "wav": "audio",
        "ogg": "audio",
        "m4a": "audio",
        "flac": "audio",
        "aac": "audio",
        "jpg": "photo",
        "jpeg": "photo",
        "png": "photo",
        "webp": "photo",
        "bmp": "photo",
    }

    try:
        ext = filename.split(".")[-1].lower()
        return extension_map.get(ext)
    except Exception:
        return None


async def fetch_cobalt_links(
    media_url: str,
    api_url: str = "http://localhost:9000/",
    timeout: int = 30,
) -> List[Tuple[str, str]] | None:
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {"url": media_url, "videoQuality": "720", "downloadMode": "auto"}

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout)
    ) as session:
        async with session.post(api_url, headers=headers, json=payload) as response:
            # if response.status != 200:
            #     error_text = await response.text()
            #     raise ValueError(f"API returned {response.status}: {error_text}")
            if response.status == 200:
                data = await response.json()
                if data["status"] in ("redirect", "tunnel"):
                    media_type = determine_media_type(data["filename"])
                    if media_type:
                        return [(media_type, data["url"])]
                elif data["status"] == "picker":
                    return [(item["type"], item["url"]) for item in data["picker"]]
            # elif data["status"] == "error":
            #     raise ValueError(f"Cobalt API error: {data['error']['code']}")
            # raise ValueError(f"Unknown response status: {data['status']}")
            return None


# def calculate_video_params(direct_link: str):
#     with VideoFileClip(direct_link) as video:
#         duration = int(video.duration)
#         width, height = video.size

#         # Создание миниатюры с использованием временного файла
#         with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_thumb:
#             frame = video.get_frame(int(duration / 2))  # Кадр из середины видео
#             image = Image.fromarray(frame)
#             image.thumbnail((320, 320), Image.Resampling.LANCZOS)

#             # Сохранение миниатюры с контролем качества
#             quality = 85
#             while True:
#                 # Уменьшаем качество, если файл слишком большой
#                 image.save(temp_thumb.name, format="JPEG", quality=quality)
#                 if os.path.getsize(temp_thumb.name) <= 200 * 1024:
#                     break
#                 quality = max(10, quality - 5)
#             print(temp_thumb.name)
#             return {
#                 "video": FSInputFile(direct_link),
#                 "duration": duration,
#                 "width": width,
#                 "height": height,
#                 "thumbnail": FSInputFile(temp_thumb.name),
#             }


# def syncfunc():
#     async def asyncfunc():
#         links = await fetch_cobalt_links("https://www.youtube.com/watch?v=obc6n9U0s1E")
#         for link in links:
#             print(link)
#             await fetch_and_save(
#                 url=link[1],
#                 filename=f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}.{'jpg' if link[0] == 'photo' else 'mp4'}",
#                 max_size_mb=50,
#             )

#     asyncio.run(asyncfunc())


# syncfunc()


# async def process_downloaded_file():
#     url = "https://drive.usercontent.google.com/u/0/uc?id=1c3GLj3RbRm65A4R21NhBbOX2FjjcrYNf&export=download"  # Замените на реальный URL

#     try:
#         # Используем контекстный менеджер для загрузки
#         async with fetch_and_save_async(url) as file:
#             print(f"file: {file.name}")
#             file_size = Path(str(file.name)).stat().st_size
#             print(f"size: {file_size / (1024 * 1024):.2f} MB")
#             async with get_video_info_async(str(file.name)) as param:
#                 print(param)

#     except ValueError as e:
#         print(f"Ошибка загрузки: {e}")
#     except Exception as e:
#         print(f"Неожиданная ошибка: {e}")


# # Запуск
# asyncio.run(process_downloaded_file())
