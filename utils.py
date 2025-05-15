import httpx
import aiofiles
from pathlib import Path


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
