# Stage 1: Build/Setup Environment
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies if any (e.g., for compiling certain Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy requirements file
COPY requirements.txt .

# Install dependencies
# Using --no-cache-dir can reduce image size slightly
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./app ./app
# COPY ./app/.env . # Copy .env file. FastAPI app loads it from app/../.env

# Stage 2: Production Image (if needed for further optimization, otherwise builder can be used)
# For this simple API, we can use the builder stage directly or create a minimal final stage.
# Let's use a slim final stage.

FROM python:3.10-slim AS production

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy application code
COPY ./app ./app/
# COPY .env ./

# Expose port 8000 for Uvicorn
EXPOSE 8000

# Command to run the Uvicorn server
# Uvicorn will look for an 'app' instance in 'app.main'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
