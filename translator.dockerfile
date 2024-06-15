ARG PYTHON_VERSION=3.11.8
FROM python:${PYTHON_VERSION}-bullseye

WORKDIR /app

COPY requirements.txt requirements.txt
COPY src src

RUN pip install -r requirements.txt

ENV WEBLATE_API_KEY=""
ENV OPENAI_KEY=""

ENTRYPOINT ["python", "src/main.py"]
CMD ["--project", "--components", "--languages"]
