# Multi-stage build for production optimization
FROM python:3.11-slim 

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY models.py .
COPY activities.py .
COPY workflows.py .
COPY platform_sdk.py .
COPY main.py .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

# Expose port for metrics (optional)
EXPOSE 8082

# Default command
CMD ["python", "main.py"]