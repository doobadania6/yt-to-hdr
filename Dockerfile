# Używamy lekkiego obrazu Pythona
FROM python:3.10-slim

# Instalujemy FFmpeg wewnątrz kontenera
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Ustawiamy folder roboczy
WORKDIR /app

# Kopiujemy wymagania i instalujemy je
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiujemy kod aplikacji
COPY . .

# Uruchamiamy aplikację za pomocą gunicorn (stabilniejszy niż wbudowany serwer Flask)
CMD gunicorn --bind 0.0.0.0:$PORT app:app
