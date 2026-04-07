# Usamos la imagen oficial de Playwright
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

ENV TZ=America/Mexico_City

# Configurar el sistema para usar esa zona horaria
# Esto evita que tzdata pida interacción manual y crea el link simbólico
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps

# Comando para mantener el contenedor vivo para el Cron de Coolify
CMD ["tail", "-f", "/dev/null"]