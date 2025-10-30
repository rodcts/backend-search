FROM python:3.12-slim

# 2. Define o diretório de trabalho
WORKDIR /app

# 3. Copia e instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copia todo o código da aplicação
COPY ./app /app/app

# 5. Expõe a porta que a API vai rodar
EXPOSE 9001

# 6. Comando para iniciar o servidor Gunicorn/Uvicorn em produção
# -k uvicorn.workers.UvicornWorker: Worker assíncrono (necessário para FastAPI)
# --timeout 60: Aumenta o timeout padrão (30s) para o "Líder" ter tempo de raspar
CMD ["gunicorn", "-w", "4", "app.main:app", "-b", "0.0.0.0:9001", "--timeout", "60", "-k", "uvicorn.workers.UvicornWorker"]