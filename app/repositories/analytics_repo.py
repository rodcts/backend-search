# app/repositories/analytics_repo.py
import pymongo
from datetime import datetime
from app.core.config import MONGO_URI

# O cliente é inicializado uma vez e reutilizado
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database() # O nome 'avaliador' vem da URI
analytics_collection = db.price_analytics

def save_analytic_data(product_slug: str, price: float, raw_data: list):
    """ Salva o resultado do scraping no MongoDB para análise futura. """
    document = {
        "product_slug": product_slug,
        "price_sugerido": price,
        "data_coleta": datetime.utcnow(),
        "dados_brutos_coletados": raw_data
    }
    analytics_collection.insert_one(document)