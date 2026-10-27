FROM docker.io/library/python:3.11-slim
ARG APP_VERSION=cp1
ENV APP_VERSION=$APP_VERSION PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/
RUN useradd --uid 10001 --create-home portal
USER 10001
EXPOSE 8080
CMD ["gunicorn","--bind","0.0.0.0:8080","--workers","1","--threads","2","--access-logfile","-","--error-logfile","-","app:app"]
