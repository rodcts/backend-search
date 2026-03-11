# app/services/scraper_service.py
import asyncio
import logging  # Importar o logging
import re

import httpx
from bs4 import BeautifulSoup

from app.core.config import SCRAPE_TIMEOUT_SECONDS

log = logging.getLogger(__name__)  # Logger para este módulo

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def _get_ml_url(product_name: str, estado: str) -> str:
    """
    (CORREÇÃO) Gera a URL do Mercado Livre com o filtro de estado.
    """
    # (CORREÇÃO) Cria o slug para a URL a partir do nome limpo
    # Remove caracteres especiais e espaços múltiplos
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", product_name)
    product_url_slug = clean_name.lower().replace(" ", "-").strip()
    product_url_slug = re.sub(r"-+", "-", product_url_slug)

    base_url = f"https://lista.mercadolivre.com.br/{product_url_slug}"

    mapa_estado_ml = {
        "novo": "2230284",
        "excelente": "2230581",
        "bom": "2230581",
        "defeito": "2230582",
    }

    filtro_id = mapa_estado_ml.get(estado, "2230581")
    url_com_filtro = f"{base_url}_DisplayType_LF_ITEM_CONDITION_{filtro_id}"

    log.info(f"[Scraper] URL do ML gerada: {url_com_filtro}")
    return url_com_filtro


async def _scrape_mercado_livre(
    client: httpx.AsyncClient, product_name: str, estado: str
):
    """Componente de scraping focado no Mercado Livre, agora com filtro de estado."""

    # (MELHORIA 2) Usa a nova função para gerar a URL filtrada
    url = _get_ml_url(product_name, estado)

    log.info(
        f"[Scraper] Buscando Mercado Livre para: {product_name} (Estado: {estado})"
    )

    try:
        response = await client.get(url, headers=HEADERS, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        seletor_preco = "span.andes-money-amount__fraction"
        price_elements = soup.select(seletor_preco)

        if not price_elements:
            log.warning(
                f"[Scraper] Nenhum preço encontrado no ML para: {product_name} (Estado: {estado})"
            )
            return None

        prices = []
        for p in price_elements[:5]:  # Pega os 5 primeiros
            valor_texto = p.text.replace(".", "").replace(",", "").strip()
            if valor_texto.isdigit():
                prices.append(float(valor_texto))

        if prices:
            # O scraper agora só retorna os preços brutos.
            # A lógica de estatística foi movida para o price_service.
            log.info(f"[Scraper] ML OK. {len(prices)} preços encontrados.")
            return {"site": "mercadolivre", "prices": prices}

    except Exception as e:
        log.error(
            f"[Scraper] Falha CRÍTICA ao raspar ML para {product_name} (Estado: {estado})",
            exc_info=True,
        )
        return {"site": "mercadolivre", "error": f"failed_to_scrape: {e}"}

    return None


async def scrape_sites_in_parallel(
    product_name: str, estado: str
) -> (list | None, list):
    """
    Orquestrador do scraping. Roda todos os sites em paralelo.
    (Agora retorna uma LISTA de preços, não o preço final)
    """
    async with httpx.AsyncClient(timeout=SCRAPE_TIMEOUT_SECONDS) as client:
        tasks = [
            # (MELHORIA 2) Passa o estado para todos os scrapers
            _scrape_mercado_livre(client, product_name, estado),
            # _scrape_olx(client, product_name, estado), # (Manter comentado)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Processa os resultados
        raw_data = []
        all_prices = []

        for r in results:
            if isinstance(r, dict) and r.get("prices"):
                # Adiciona todos os preços encontrados na lista única
                all_prices.extend(r["prices"])
                raw_data.append(r)
            elif isinstance(r, dict):
                raw_data.append(r)

        if not all_prices:
            return None, raw_data  # Falha ao coletar qualquer preço

        # Retorna a lista de preços brutos e os dados brutos
        return all_prices, raw_data
