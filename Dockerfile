# Dockerfile para PortoEx - Flask + Gunicorn
FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 5000

CMD ["gunicorn", "improved_chico_automate_fpdf:app", "--bind", "0.0.0.0:5000"] 