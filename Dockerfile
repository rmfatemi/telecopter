FROM python:3.11-alpine

WORKDIR /app

RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev && \
    apk add --no-cache libffi && \
    pip install --upgrade pip && \
    pip install poetry

    COPY pyproject.toml poetry.lock* README.md ./

COPY telecopter ./telecopter

RUN poetry config virtualenvs.create false && \
    poetry install --without dev && \
    apk del .build-deps

COPY . .

CMD ["telecopter"]
