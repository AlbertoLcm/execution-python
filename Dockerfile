# 1. Usamos la imagen oficial de Playwright
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# 2. Instalar tzdata (para la zona horaria) y Tini (para evitar procesos zombis)
# DEBIAN_FRONTEND=noninteractive evita que la instalación de tzdata pause el build pidiendo confirmación
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Instalación de dependencias
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

# 4. El "Secreto": Tini como Entrypoint
# Tini se convierte en el PID 1 y gestiona correctamente las señales y procesos hijos
ENTRYPOINT ["/usr/bin/tini", "--"]

# 5. Mantener el contenedor vivo para el Cron
CMD ["tail", "-f", "/dev/null"]