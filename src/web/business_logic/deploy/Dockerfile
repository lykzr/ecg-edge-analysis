FROM python:3.12-slim
WORKDIR /app
COPY business_logic/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY business_logic /app/business_logic
COPY signal_processing /app/signal_processing
COPY hardware /app/hardware
COPY ai_model /app/ai_model
ENV PYTHONPATH=/app:/app/business_logic
ENV HEALTH_DB_PATH=/app/runtime/health.sqlite3
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
