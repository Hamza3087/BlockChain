# Sugar CLI environment for Candy Machine v3 on devnet
FROM rust:1.75-bullseye

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config libssl-dev libudev-dev ca-certificates git curl \
    && rm -rf /var/lib/apt/lists/*

# Install Solana CLI (needed for some sugar ops)
RUN sh -c "curl -sSfL https://release.solana.com/v1.18.26/install | bash -s -" \
    && /bin/bash -lc "echo 'export PATH=\"/root/.local/share/solana/install/active_release/bin:$PATH\"' >> /root/.bashrc"

ENV PATH="/root/.local/share/solana/install/active_release/bin:${PATH}"

# Install sugar CLI
RUN cargo install --locked sugar-cli@2.8.1 || cargo install --locked sugar-cli

WORKDIR /workspace

ENTRYPOINT ["/bin/bash","-lc"]
CMD ["sugar --version"]

