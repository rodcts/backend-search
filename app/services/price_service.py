# app/services/price_service.py
import asyncio
import time
import pandas as pd # Importar pandas aqui
import logging
from app.repositories import cache_repo, analytics_repo
from app.services import scraper_service

log = logging.getLogger(__name__)

def _slugify_cache_key(product_name: str, estado: str) -> str:
    """ Gera a chave para o cache (incluindo o estado). """
    return f"{product_name.lower().replace(' ', '-').strip()}:{estado}"

def _calculate_price_stats(prices: list) -> dict:
    """
    (MELHORIA 3) Calcula a resposta detalhada (Média Aparada).
    Esta é a lógica que movemos do scraper_service para cá.
    """
    series = pd.Series(prices)
    
    # Estatísticas básicas
    count = len(series)
    price_min = float(series.min())
    price_max = float(series.max())

    # Lógica da "Média Aparada" (o "preço sugerido")
    if count < 3:
        price_sug = float(series.median())
    else:
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        trimmed_series = series[(series >= q1) & (series <= q3)]
        
        if trimmed_series.empty:
            price_sug = float(series.median())
        else:
            price_sug = float(trimmed_series.mean())

    return {
        "preco_sugerido": round(price_sug, 2),
        "preco_min": round(price_min, 2),
        "preco_max": round(price_max, 2),
        "anuncios_analisados": count
    }

async def get_fresh_price_stats(product_name: str, estado: str) -> dict | None:
    """
    Orquestra a busca de preços, agora retornando um dicionário de estatísticas.
    """
    # (CORREÇÃO) Gera a chave de cache, mas mantém o product_name original
    product_cache_key = _slugify_cache_key(product_name, estado)
    
    # 1. Tenta buscar do Micro-Cache
    cached_stats = cache_repo.get_price_from_cache(product_cache_key)
    if cached_stats:
        log.info(f"Cache HIT para: {product_cache_key}")
        return cached_stats 

    # 2. CACHE MISS. Tenta adquirir a trava.
    if cache_repo.acquire_lock(product_cache_key):
        log.info(f"Cache MISS. {product_cache_key} se tornou Líder.")
        try:
            # (CORREÇÃO) Passa o product_name LIMPO e o estado para o scraper
            prices, raw_data = await scraper_service.scrape_sites_in_parallel(product_name, estado)
            
            if prices:
                stats = _calculate_price_stats(prices)
                
                # Salva no Cache Rápido (usando a chave de cache)
                cache_repo.set_price_in_cache(product_cache_key, stats)
                # Salva no BD Analítico (usando a chave de cache)
                analytics_repo.save_analytic_data(product_cache_key, stats, raw_data)
                
                return stats
            else:
                return None # Scraping falhou
        finally:
            # Libera a trava (usando a chave de cache)
            cache_repo.release_lock(product_cache_key)
    else:
        # 2B. FALHA: Nós somos "Seguidores".
        log.info(f"Cache LOCK. {product_cache_key} se tornou Seguidor.")
        return await _wait_for_leader_to_finish(product_cache_key)


async def _wait_for_leader_to_finish(product_cache_key: str, timeout_seconds: int = 20) -> dict | None:
    """
    Lógica do "Seguidor". (Agora usa a chave de cache correta)
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout_seconds:
        # (CORREÇÃO) Usa a chave de cache
        cached_stats = cache_repo.get_price_from_cache(product_cache_key)
        if cached_stats:
            log.info(f"Seguidor {product_cache_key} encontrou o cache do Líder.")
            return cached_stats
        
        await asyncio.sleep(0.5) 
    
    log.warning(f"Seguidor {product_cache_key} atingiu o timeout esperando pelo Líder.")
    return None