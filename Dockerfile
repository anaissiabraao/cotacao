# Dockerfile para PortoEx - Flask + Gunicorn
FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8000

CMD ["gunicorn", "app2:app", "--bind", "0.0.0.0:8000"] 