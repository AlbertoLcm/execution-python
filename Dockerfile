# 1. Usamos la imagen oficial de Playwright
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# 2. Configurar Zona Horaria (México)
ENV TZ=America/Mexico_City
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 3. Instalar Tini para evitar procesos zombis
RUN apt-get update && apt-get install -y tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 4. Instalación de dependencias
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

# 5. El "Secreto": Tini como Entrypoint
# Tini se convierte en el PID 1 y gestiona correctamente las señales y procesos hijos
ENTRYPOINT ["/usr/bin/tini", "--"]

# 6. Mantener el contenedor vivo para el Cron
CMD ["tail", "-f", "/dev/null"]