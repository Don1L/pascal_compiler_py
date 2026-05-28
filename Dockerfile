FROM python:3.11-slim

# Устанавливаем NASM и 32-bit gcc
RUN apt-get update && apt-get install -y \
    nasm \
    gcc \
    gcc-multilib \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Python
RUN pip install lark

# Копируем проект
WORKDIR /pascal
COPY . .

ENTRYPOINT ["python", "run.py"]
