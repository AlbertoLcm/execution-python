# Usamos la imagen oficial que ya trae Python y los navegadores instalados
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

CMD ["python", "main.py"]