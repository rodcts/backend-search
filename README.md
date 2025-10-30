# API Avaliador de Preços (Backend)

Backend de alta performance para avaliação de preços de produtos usados em tempo real, construído com FastAPI, Redis e MongoDB.

Esta API é projetada para ser consumida por um aplicativo móvel (React Native), priorizando a entrega de dados frescos (coletados em tempo real) e protegendo o servidor contra bloqueios de IP e sobrecarga através de uma arquitetura de cache resiliente.

## Arquitetura do Projeto

O principal desafio deste projeto é equilibrar a necessidade do usuário por **dados frescos** (coletados no momento da solicitação) com a realidade técnica do **Web Scraping**, que é um processo lento, frágil e sujeito a bloqueios de IP.

Uma arquitetura simples (onde 100 usuários acionam 100 _scrapers_) falharia em minutos. Por isso, implementamos uma arquitetura de alta resiliência baseada em 3 componentes principais:

1.  **FastAPI (com Gunicorn/Uvicorn):** A camada de API. Escolhido no lugar do Flask por seu suporte nativo a `asyncio`, permitindo que o _scraping_ de múltiplos sites (ML, OLX, etc.) seja feito em **paralelo** (assíncrono), reduzindo o tempo de espera de ~15s para ~5s.
2.  **Redis (Cache Rápido):** Usado para duas funções críticas:
    - **Micro-Cache (ex: 5 minutos):** Para atender à regra de negócio de dados frescos. Se 100 usuários buscarem o mesmo item em 5 minutos, apenas o primeiro acionará o _scraping_. Os outros 99 receberão a resposta instantânea do cache, protegendo o servidor de ser banido por _rate limiting_.
    - **Cache Lock (Trava):** Para resolver o "Problema do Estouro da Manada" (Thundering Herd Problem). Quando o cache de 5 minutos expira, apenas a _primeira_ requisição ("Líder") tem permissão para fazer o _scraping_. As outras ("Seguidoras") esperam o Líder preencher o cache, evitando que 100 usuários acionem 100 _scrapers_ ao mesmo tempo.
3.  **MongoDB (Banco de Dados Analítico):** Usado como um banco de dados "só de escrita" (write-only) pela perspectiva do usuário. Cada _scraping_ bem-sucedido é salvo no MongoDB para permitir análises de _timeline_ e histórico de preços, conforme solicitado.

### O Fluxo da Requisição

1.  **Request (App Móvel)** → `FastAPI`
2.  `FastAPI` → `Redis` (Verifica o Micro-Cache de 5 min)
3.  **Cenário A (Cache HIT):** `Redis` → `FastAPI` → `App Móvel`. **(Resposta < 1s)**
4.  **Cenário B (Cache MISS):**
    a. `FastAPI` → `Redis` (Tenta adquirir "Cache Lock").
    b. **Se "Líder":**
    i. `FastAPI` → Inicia _Scraping_ Paralelo (`httpx`).
    ii. `Scraping` → Calcula o Preço.
    iii. `Scraping` → Salva no `Redis` (com expiração de 5 min).
    iv. `Scraping` → Salva no `MongoDB` (para analytics).
    v. `FastAPI` → `App Móvel`. **(Resposta em 5-7s)**
    c. **Se "Seguidor":**
    i. `FastAPI` → Espera/Verifica o `Redis` (loop de 500ms).
    ii. `Redis` (preenchido pelo Líder) → `FastAPI` → `App Móvel`. **(Resposta em 1-7s)**

## Estrutura de Pastas

O projeto segue princípios de Clean Code, separando responsabilidades em camadas (API, Serviço, Repositório).

avaliador_backend/
├── app/
│   ├── __init__.py
│   ├── main.py               # Camada da API (FastAPI) - Ponto de Entrada
│   ├── services/
│   │   ├── __init__.py
│   │   ├── price_service.py    # Camada de Serviço (Lógica de Negócio e Cache-Lock)
│   │   └── scraper_service.py  # Camada de Infra (Lógica de Scraping Paralelo)
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── cache_repo.py       # Camada de Infra (Comunicação com Redis)
│   │   └── analytics_repo.py   # Camada de Infra (Comunicação com MongoDB)
│   └── core/
│       ├── __init__.py
│       └── config.py           # Configurações (Constantes, Chaves, URIs)
│
├── requirements.txt            # Dependências Python (local correto)
├── podmanfile                  # Instruções para construir a imagem da API
└── podman-compose.yml          # Orquestrador (Sobe a API + Redis + MongoDB)

## Descrição dos Módulos

| Arquivo/Pasta                            | Responsabilidade (Single Responsibility Principle)                                                                                                                                                  |
| :--------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`app/main.py`**                        | **Camada de API.** Lida com o protocolo HTTP. Recebe as requisições, valida os dados de entrada (usando Pydantic), configura o CORS e chama a camada de serviço (`price_service`).                  |
| **`app/services/price_service.py`**      | **Camada de Serviço.** Orquestra a regra de negócio principal. É responsável por implementar o fluxo de "Cache Lock" (Líder/Seguidor) e decidir quando buscar do cache ou acionar o _scraping_.     |
| **`app/services/scraper_service.py`**    | **Camada de Infraestrutura (Scraping).** Lida com a lógica "suja" de _scraping_. Usa `httpx` e `asyncio` para buscar dados em paralelo de múltiplos sites e `BeautifulSoup` para extrair os preços. |
| **`app/repositories/cache_repo.py`**     | **Camada de Repositório (Cache).** Isola toda a comunicação com o Redis. Contém funções `get`, `set`, `acquire_lock` e `release_lock`.                                                              |
| **`app/repositories/analytics_repo.py`** | **Camada de Repositório (BD).** Isola toda a comunicação com o MongoDB. Contém a função `save_analytic_data` para salvar o histórico.                                                               |
| **`app/core/config.py`**                 | **Configuração.** Armazena constantes (URIs de conexão, tempos de expiração de cache) lidas das variáveis de ambiente.                                                                              |
| **`podmanfile`**                         | **Deployment.** Script para construir a imagem podman da aplicação FastAPI/Gunicorn.                                                                                                                |
| **`podman-compose.yml`**                 | **Orquestração.** Arquivo essencial para o ambiente de desenvolvimento, responsável por "levantar" os 3 serviços (API, Redis, MongoDB) e conectá-los na mesma rede.                                 |

## Como Usar (Comandos)

Esta aplicação é projetada para rodar com podman e podman Compose, o que gerencia a API, o Redis e o MongoDB automaticamente.

### Pré-requisitos

- [podman Desktop](https://www.podman.com/products/podman-desktop/) instalado e rodando.

### Passo 1: Criar o `podman-compose.yml`

O `podmanfile` (que você já tem) constrói a API. O `podman-compose.yml` (abaixo) conecta a API aos bancos de dados. Crie este arquivo na raiz do seu projeto (`avaliador_backend/`).

**`podman-compose.yml`**

```yaml
version: "3.8"

services:
  # 1. A API Python/FastAPI
  api:
    build: . # Constrói a partir do podmanfile na pasta atual
    container_name: avaliador-api
    ports:
      - "9001:9001" # Mapeia a porta do seu PC para a porta do container
    environment:
      # Passa as variáveis de ambiente para o config.py
      - REDIS_HOST=redis_cache
      - MONGO_URI=mongodb://mongodb_db:27017/avaliador
    depends_on:
      - redis_cache
      - mongodb_db
    networks:
      - avaliador-net

  # 2. O Banco de Dados Cache
  redis_cache:
    image: "redis:7-alpine"
    container_name: redis_cache
    networks:
      - avaliador-net

  # 3. O Banco de Dados Analítico
  mongodb_db:
    image: "mongo:latest"
    container_name: mongodb_db
    ports:
      - "27017:27017" # Opcional: expor o Mongo para seu PC
    networks:
      - avaliador-net

networks:
  avaliador-net:
    driver: bridge
```

### Passo 2: Levantar a Aplicação

Com todos os arquivos (app/, podmanfile, requirements.txt, podman-compose.yml) na mesma pasta, abra um terminal e execute:

```bash
podman-compose up -d --build
```

up: Inicia os containers.
-d: Roda em modo "detached" (em segundo plano).
--build: Força o podman a reconstruir sua imagem da API com qualquer nova alteração no código Python.

### Passo 3: Testar a API

Seu Backend está agora rodando na porta 9001 do seu computador (localhost). Você pode testá-lo com um cliente de API (como o Postman) ou via curl no terminal:

```bash
curl -X POST http://localhost:9001/avaliar \
```

-H "Content-Type: application/json" \
-d '{"produto": "iphone 11 64gb usado"}'

Resultado Esperado (Após alguns segundos):

```json
{ "preco_sugerido": 1500.0 }
```

### Passo 4: Conectar o Frontend (React Native)

No seu aplicativo React Native (app/index.js), use o IP da sua máquina na rede local (não localhost) e a porta 9001 para se conectar ao container:

// Ex: const API_URL = '[http://192.168.1.15:9001/avaliar](http://192.168.1.15:9001/avaliar)';

### Passo 5: Parar a Aplicação

Para desligar todos os 3 containers (API, Redis, Mongo), execute:

```bash
podman-compose down
```
