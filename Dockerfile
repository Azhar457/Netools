# Multi-stage lightweight container for Netools CLI & Services
FROM python:3.12-slim-bookworm

LABEL maintainer="Azhar <azhar@netools.local>"
LABEL description="⚡ Netools Suite: Sing-box Proxy Rotator, GRC DNS Benchmark, DNS Switcher & PAC Server"

# Install runtime dependencies (curl for upstream testing, sing-box)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install latest sing-box binary
ARG SING_BOX_VERSION=1.11.4
RUN curl -fsSL "https://github.com/SagerNet/sing-box/releases/download/v${SING_BOX_VERSION}/sing-box-${SING_BOX_VERSION}-linux-amd64.tar.gz" \
    | tar -xz --strip-components=1 -C /usr/local/bin "sing-box-${SING_BOX_VERSION}-linux-amd64/sing-box" \
    && chmod +x /usr/local/bin/sing-box

WORKDIR /app

# Copy dependency specifications
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -e .

# Copy application source code
COPY . .

# Expose default ports (PAC Server 18080, Web App 18081, Sing-box SOCKS5 11080-11099, HTTP 21080-21099)
EXPOSE 18080 18081 11080-11099 21080-21099

ENTRYPOINT ["netools"]
CMD ["proxy", "status"]
