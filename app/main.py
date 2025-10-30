# app/main.py
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from enum import Enum
from app.services import price_service

# --- Configuração do Logging ---
# Configura o logger para imprimir no console (que o Docker captura)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
# Obtém o logger para este módulo
log = logging.getLogger(__name__)
# -------------------------------


# Cria a instância principal da aplicação
app = FastAPI(
    title="Avaliador de Preços API",
    description="API para avaliar preços de produtos usados em tempo real."
)

# Adiciona o CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- NOVOS MODELOS DE DADOS (Pydantic) ---

class EstadoConservacao(str, Enum):
    """ Define as opções de estado que o Frontend pode enviar. """
    NOVO = "novo"
    EXCELENTE = "excelente"
    BOM = "bom"
    DEFEITO = "defeito"

class AvaliacaoRequest(BaseModel):
    """ O que o Frontend nos envia. """
    produto: str
    estado: EstadoConservacao = Field(
        default=EstadoConservacao.BOM,
        description="Estado de conservação do produto."
    )
    # (Opcional) Poderíamos adicionar 'categoria' aqui no futuro

class AvaliacaoResponse(BaseModel):
    """ (MELHORIA 3) O que a API retorna para o Frontend. """
    preco_sugerido: float
    preco_min: float
    preco_max: float
    anuncios_analisados: int

# --- ATUALIZAÇÃO DO ENDPOINT ---

@app.post("/avaliar", response_model=AvaliacaoResponse)
async def avaliar_produto_endpoint(request: AvaliacaoRequest):
    """
    Recebe o nome de um produto E SEU ESTADO, orquestra a avaliação 
    e retorna uma análise detalhada de preços.
    """
    log.info(f"Iniciando avaliação para: {request.produto} (Estado: {request.estado})")

    if not request.produto:
        raise HTTPException(status_code=400, detail="O campo 'produto' é obrigatório.")
    
    try:
        # (MELHORIA 2) Passamos o estado para a camada de serviço
        stats = await price_service.get_fresh_price_stats(request.produto, request.estado)
        
        if stats and stats.get("preco_sugerido"):
            log.info(f"Avaliação concluída para: {request.produto}. Preço: {stats['preco_sugerido']}")
            return AvaliacaoResponse(**stats) # Retorna o dicionário completo
        else:
            log.warning(f"Scraper falhou em coletar dados para: {request.produto}")
            raise HTTPException(status_code=503, detail="Não foi possível avaliar o produto no momento.")
    
    except Exception as e:
        log.error(f"Erro 500 ao avaliar: {request.produto}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro interno no servidor.")