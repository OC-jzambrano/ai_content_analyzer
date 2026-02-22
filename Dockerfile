FROM python:3.11-slim

WORKDIR /app

# Copy project metadata
COPY pyproject.toml README.md ./

# Install dependencies
RUN pip install --upgrade pip && pip install .

# Copy source code
COPY src ./src

# Make src available as module root
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["hypercorn", "--bind", "0.0.0.0:8000", "app.main:app"]