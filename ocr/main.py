from fastapi import FastAPI, File, UploadFile
import numpy as np
import cv2
from paddleocr import PaddleOCR

app = FastAPI()

# Load model once at startup into GPU memory
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True)

@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    # 1. Read bytes
    contents = await file.read()

    # 2. Decode bytes to numpy array (In-Memory)
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 3. Inference
    result = ocr_engine.ocr(img, cls=True)

    # 4. Format Output (Reconstruct text block)
    full_text = []
    if result and result[0]:
        for line in result[0]:
            text = line[1][0]
            full_text.append(text)

    return {"text": "\n".join(full_text)}