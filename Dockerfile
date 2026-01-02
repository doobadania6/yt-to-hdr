FROM python:3.10-slim

# Instalacja FFmpeg - kluczowe do wycinania klatek
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalacja bibliotek Pythona
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie reszty plików
COPY . .

# Uruchomienie aplikacji przez profesjonalny serwer Gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 120 app:app
