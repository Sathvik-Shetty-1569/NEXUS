FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt .

# Install CPU-only torch FIRST -- otherwise pip pulls the default GPU
# build (2GB+ of unused CUDA/NVIDIA libraries), since neither Docker
# Desktop nor Render's servers have a GPU to use it with anyway.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN mkdir -p /code/data

EXPOSE 8000

# Render (and similar PaaS) inject $PORT and expect the app to bind to it;
# default to 8000 for local docker-compose use where $PORT isn't set.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]