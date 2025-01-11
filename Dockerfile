FROM python:3.13-slim

# Install poetry
RUN pip install poetry

# Copy poetry files
WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Configure poetry to not create a virtual environment in the container
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-root --without dev --no-interaction --no-ansi

# Copy application code
COPY ski_calendar_generator ./ski_calendar_generator

# Run the application
CMD ["poetry", "run", "uvicorn", "ski_calendar_generator.api:app", "--host", "0.0.0.0", "--port", "8000"]