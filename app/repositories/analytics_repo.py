# app/repositories/analytics_repo.py
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import MONGO_URI

# O cliente é inicializado uma vez e reutilizado
client = AsyncIOMotorClient(MONGO_URI)
db = client.get_database()  # O nome 'avaliador' vem da URI
analytics_collection = db.price_analytics


async def save_analytic_data(product_slug: str, stats: dict, raw_data: list):
    """Salva o resultado do scraping no MongoDB para análise futura."""
    document = {
        "product_slug": product_slug,
        "preco_sugerido": stats.get("preco_sugerido"),
        "estatisticas_completas": stats,
        "data_coleta": datetime.utcnow(),
        "dados_brutos_coletados": raw_data,
    }
    await analytics_collection.insert_one(document)
