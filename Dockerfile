# Używamy lekkiego obrazu Python
FROM python:3.11-slim

# Ustawiamy zmienne środowiskowe dla Pythona
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Ustawiamy katalog roboczy
WORKDIR /app

# Instalujemy zależności systemowe (jeśli potrzebne, np. dla Postgresa czy kryptografii)
# Dla SQLite i czystego Pythona zazwyczaj wystarczy clean image, ale curl się przydaje do healthchecków
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Kopiujemy requirements i instalujemy biblioteki
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tworzymy użytkownika 'oltuser' (UID 1000), aby nie działać jako root
RUN groupadd -r oltuser && useradd -r -g oltuser -u 1000 oltuser

# Kopiujemy kod aplikacji
COPY . .

# Kopiujemy skrypt startowy i nadajemy uprawnienia
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Tworzymy katalog na dane (wolumen) i nadajemy uprawnienia użytkownikowi
RUN mkdir -p /data && chown -R oltuser:oltuser /data /app

# Przełączamy się na bezpiecznego użytkownika
USER oltuser

# Wystawiamy port
EXPOSE 5000

# Definiujemy punkt startowy
ENTRYPOINT ["/entrypoint.sh"]