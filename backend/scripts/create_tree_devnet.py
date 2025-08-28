#!/usr/bin/env python3
import os
import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from blockchain.clients.real_onchain_client import RealOnChainClient

async def main():
    keypair_path = os.environ.get("SOLANA_KEYPAIR") or os.environ.get("FUNDED_WALLET_PATH")
    if not keypair_path:
        print(json.dumps({"status": "error", "error": "SOLANA_KEYPAIR env not set"}))
        return

    client = RealOnChainClient(
        rpc_url="https://api.devnet.solana.com",
        funded_account_secret=keypair_path,
    )
    async with client:
        res = await client.create_merkle_tree(max_depth=14, max_buffer_size=64)
        print(json.dumps(res))

if __name__ == "__main__":
    asyncio.run(main())

