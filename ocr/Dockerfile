FROM python:3.10-slim

# Install system dependencies for OpenCV and Paddle
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
RUN pip install paddlepaddle-gpu==2.6.1 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
RUN pip install "paddleocr>=2.7" opencv-python-headless fastapi uvicorn python-multipart

COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]