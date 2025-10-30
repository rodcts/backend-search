# app/core/config.py
import os

# Configurações do Banco de Dados
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/avaliador")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Regras de Negócio (Micro-Cache)
CACHE_EXPIRATION_SECONDS = 300 # 5 minutos
LOCK_EXPIRATION_SECONDS = 30   # Tempo máximo que um scraper "Líder" pode travar o lock
SCRAPE_TIMEOUT_SECONDS = 10    # Timeout para cada site (ML, OLX...)