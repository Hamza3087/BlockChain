#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SOLANA_KEYPAIR:-}" && -z "${FUNDED_WALLET_PATH:-}" ]]; then
  echo "Please export SOLANA_KEYPAIR or FUNDED_WALLET_PATH pointing to your keypair JSON (e.g., /home/hamza/my_devnet_wallet.json)" >&2
  exit 1
fi

KEYPAIR_PATH="${SOLANA_KEYPAIR:-${FUNDED_WALLET_PATH}}"

cd "$(dirname "$0")/.."

echo "Using keypair: $KEYPAIR_PATH"
solana config set --url https://api.devnet.solana.com >/dev/null

# 1) Build assets from latest Sei export
python3 scripts/build_assets_from_sei.py

# 2) Upload assets
npx @metaplex/cli upload ./assets --env devnet --keypair "$KEYPAIR_PATH" --rpc-url https://api.devnet.solana.com

# 3) Create candy machine
npx @metaplex/cli create_candy_machine --env devnet --keypair "$KEYPAIR_PATH" --rpc-url https://api.devnet.solana.com --price 0.001

# 4) Go live now
npx @metaplex/cli update_candy_machine --env devnet --keypair "$KEYPAIR_PATH" --rpc-url https://api.devnet.solana.com --date "now"

# 5) Mint a token
npx @metaplex/cli mint_one_token --env devnet --keypair "$KEYPAIR_PATH" --rpc-url https://api.devnet.solana.com

echo "Deployment complete. Check .cache/devnet for candy machine ID and minted address."

