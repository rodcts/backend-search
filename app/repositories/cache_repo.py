# app/repositories/cache_repo.py
import json  # Importar JSON

import redis.asyncio as redis

from app.core.config import (
    CACHE_EXPIRATION_SECONDS,
    LOCK_EXPIRATION_SECONDS,
    REDIS_HOST,
    REDIS_PORT,
)

redis_pool = redis.ConnectionPool(
    host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
)
redis_client = redis.Redis(connection_pool=redis_pool)


def _get_connection():
    return redis_client


async def get_price_from_cache(product_slug: str) -> dict | None:
    """Busca um preço no cache. (Agora retorna um DICT)"""
    r = _get_connection()
    cached_data = await r.get(f"price:{product_slug}")
    if cached_data:
        try:
            # Desserializa o JSON salvo no cache
            return json.loads(cached_data)
        except json.JSONDecodeError:
            return None
    return None


async def set_price_in_cache(product_slug: str, stats: dict):
    """Define as estatísticas (DICT) no cache."""
    r = _get_connection()
    # Serializa o dicionário para JSON antes de salvar
    stats_json = json.dumps(stats)
    await r.set(f"price:{product_slug}", stats_json, ex=CACHE_EXPIRATION_SECONDS)


# ... (Funções de acquire_lock e release_lock permanecem as mesmas) ...
async def acquire_lock(product_slug: str) -> bool:
    r = _get_connection()
    return await r.set(f"lock:{product_slug}", "1", nx=True, ex=LOCK_EXPIRATION_SECONDS)


async def release_lock(product_slug: str):
    r = _get_connection()
    await r.delete(f"lock:{product_slug}")
