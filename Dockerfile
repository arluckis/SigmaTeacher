# Usa uma imagem leve do Python 3.10
FROM python:3.10-slim

# 1. Instala o FFmpeg (O pulo do gato para o Whisper funcionar no Docker)
# O 'apt-get' é o instalador de programas do Linux
RUN apt-get update && apt-get install -y ffmpeg

# 2. Cria uma pasta de trabalho dentro do container
WORKDIR /app

# 3. Copia a lista de ingredientes primeiro (pra ser mais rápido)
COPY requirements.txt .

# 4. Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia todo o resto do seu projeto para dentro do container
COPY . .

# Expõe as portas que vamos usar
EXPOSE 8000
EXPOSE 8501