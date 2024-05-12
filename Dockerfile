# Use a builder image for compiling and preparing the application
FROM python:3.11-slim AS builder
WORKDIR /app

# Copy only the requirements-lock.txt initially to leverage Docker cache
COPY ./app/requirements-lock.txt /app/

# Install dependencies
RUN pip install --target=/app -r requirements-lock.txt

# Copy the rest of the application code
COPY ./app /app

# Use a distroless image for running the application
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["/app/main.py"]
