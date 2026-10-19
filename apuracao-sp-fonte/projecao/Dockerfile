FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV PYTHONUNBUFFERED=1 TZ=America/Sao_Paulo SAIDA=/data/live THREADS=128
CMD ["python3", "-u", "coletor.py"]
