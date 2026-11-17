FROM python:3.12.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py conversacion.py ./
COPY templates/ templates/
COPY static/ static/
EXPOSE 8501
CMD ["gunicorn", "--bind", "0.0.0.0:8501", "--workers", "2", "--threads", "4", "--timeout", "60", "app:app"]
