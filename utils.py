from httpx import AsyncClient
from aiofiles import tempfile
import asyncio
from aiohttp import ClientSession, ClientTimeout
from typing import List, Tuple, Optional, Literal, Dict
from contextlib import asynccontextmanager
from io import BytesIO
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
    buffer = BytesIO()
    try:
        async with AsyncClient(timeout=30.0) as client:
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
async def get_video_info_from_buffer_async(buffer: BytesIO):
    def sync_video_analysis(video_path: str):
        cap = cv2.VideoCapture(video_path)
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            _, first_frame = cap.read()
            frame_count = sum(1 for _ in iter(cap.grab, False))
            duration = round(frame_count / fps) if fps > 0 else 0
            return duration, width, height, first_frame
        finally:
            cap.release()

    async with tempfile.NamedTemporaryFile("wb") as temp_file:
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

    async with ClientSession(timeout=ClientTimeout(total=timeout)) as session:
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
