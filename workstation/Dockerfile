# Disposable developer workstation: both agent CLIs, pinned, plus the lab's recorders.
FROM node:22-bookworm-slim
ARG CLAUDE_CODE_VERSION=2.1.220
ARG CODEX_VERSION=0.162.1
RUN apt-get update && apt-get install -y --no-install-recommends \
      strace tcpdump curl ca-certificates git python3 procps ripgrep \
      bubblewrap socat iptables \
    && rm -rf /var/lib/apt/lists/*
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} @openai/codex@${CODEX_VERSION} \
    && npm cache clean --force
RUN usermod -l dev -d /home/dev -m -s /bin/bash node && groupmod -n dev node
COPY workstation/ /opt/lab/
COPY common/ /opt/lab/
COPY fixtures/ /opt/lab/fixtures/
RUN chmod +x /opt/lab/*.sh
ENTRYPOINT ["/opt/lab/run.sh"]
