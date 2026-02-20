# ==============================================================
# nogil-bench Dockerfile
# CPython 3.14 free-threaded 소스 빌드 (--disable-gil)
# 구조: builder → base → test → production
# ==============================================================

# ---- Builder: CPython free-threaded 빌드 ----
FROM python:3.14-slim AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.14.3

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libssl-dev \
    libffi-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    liblzma-dev \
    tk-dev \
    uuid-dev \
    libgdbm-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz \
        | tar xz \
    && cd Python-${PYTHON_VERSION} \
    && ./configure \
        --disable-gil \
        --prefix=/opt/python-ft \
    && make -j$(nproc) \
    && make install \
    && cd .. && rm -rf Python-${PYTHON_VERSION}

# ---- Base: 런타임 환경 ----
FROM python:3.14-slim AS base

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul

RUN apt-get update && apt-get install -y tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# free-threaded Python 복사 + 검증
COPY --from=builder /opt/python-ft /opt/python-ft
ENV PATH="/opt/python-ft/bin:$PATH"
ENV PYTHON_GIL=0

RUN python3 -c "\
import sysconfig, sys; \
assert sysconfig.get_config_var('Py_GIL_DISABLED') == 1, 'Not a free-threaded build'; \
print(f'Python {sys.version}'); \
print(f'GIL disabled: {not sys._is_gil_enabled()}')"

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml ./
RUN uv sync --no-cache

# ---- Test (CI용, Day 4에서 활성화) ----
FROM base AS test

# ---- Production (Day 6에서 활성화) ----
FROM base AS production
