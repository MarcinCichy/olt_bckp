#!/bin/sh

# Przejdź do katalogu aplikacji
cd /app

# Jeśli baza danych nie istnieje w wolumenie /data, zainicjuj ją
if [ ! -f "/data/app.db" ]; then
    echo "--> Baza danych nie istnieje. Inicjalizacja..."
    python -m flask --app webapp init-db
fi

# Zawsze próbuj zaktualizować schemat (dla bezpieczeństwa przy aktualizacjach)
echo "--> Aktualizacja schematu bazy danych..."
python -m flask --app webapp update-schema

# Uruchom serwer produkcyjny Gunicorn
# -w 4 : 4 procesy (workerów)
# -b 0.0.0.0:5000 : nasłuchuj na porcie 5000
echo "--> Start serwera Gunicorn..."
exec gunicorn -w 4 -b 0.0.0.0:5000 webapp:app