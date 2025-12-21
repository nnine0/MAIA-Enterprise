from celery_app import celery_app
import httpx
from main import execute_maia_protocol
import config

@celery_app.task
def process_ocr_and_analyze(image_bytes: bytes, filename: str, content_type: str) -> dict:
    # Process OCR
    async def ocr():
        async with httpx.AsyncClient() as client:
            files = {'file': (filename, image_bytes, content_type)}
            r = await client.post(f"{config.OCR_URL}/ocr", files=files, timeout=300.0)
            r.raise_for_status()
            return r.json().get("text", "")

    # Since Celery is sync, need to run async code
    import asyncio
    ocr_text = asyncio.run(ocr())

    if ocr_text:
        # Analyze with MAIA
        response = asyncio.run(execute_maia_protocol(f"Analyze this document content: {ocr_text}"))
        return {"ocr_text": ocr_text, "response": response}
    return {"error": "OCR failed"}