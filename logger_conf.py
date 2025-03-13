# logger_conf.py

import logging
import colorlog

# Definicja formatu logów z kolorami
log_format = "%(log_color)s%(levelname)-8s%(reset)s %(message)s"
logger = logging.getLogger()  # Pobranie globalnego loggera
handler = colorlog.StreamHandler()

# Ustawienie poziomu logowania na DEBUG, aby wyświetlać szczegółowe komunikaty
logger.setLevel(logging.DEBUG)

formatter = colorlog.ColoredFormatter(log_format)
handler.setFormatter(formatter)

# Dodanie handlera do loggera
logger.addHandler(handler)
