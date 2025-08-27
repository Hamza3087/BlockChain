#!/bin/bash

echo "🔍 SOLANA DEVNET MIGRATION VERIFICATION"
echo "========================================"
echo ""

# Tree addresses from recent migrations
TREE_ADDRESS_1="H9nW5bwXxrYsuqtxAsHGGBxhxCumEyPDzE1hXq7wVat"
TREE_ADDRESS_2="8HPi86nGtWjCLmKaQ4x9zjFTJuyMumbwK2HxcFnV3jFm"

# Mint addresses from recent migrations
MINT_ADDRESS_1="C5kRHy5TNHd8X7cC1yiKn7qARPK6sj7tg9ZvM89XJiek"
MINT_ADDRESS_2="7uso6T5X8TTRUYLvY91maAdZbQCMUskyZbCfZtN3r6jW"

echo "🌳 VERIFYING MERKLE TREE ACCOUNTS"
echo "================================="

echo "1. Checking Tree Address: $TREE_ADDRESS_1"
solana account $TREE_ADDRESS_1 --url https://api.devnet.solana.com
echo ""

echo "2. Checking Tree Address: $TREE_ADDRESS_2"
solana account $TREE_ADDRESS_2 --url https://api.devnet.solana.com
echo ""

echo "🎯 VERIFYING MINT ADDRESSES"
echo "==========================="

echo "1. Checking Mint Address: $MINT_ADDRESS_1"
solana account $MINT_ADDRESS_1 --url https://api.devnet.solana.com
echo ""

echo "2. Checking Mint Address: $MINT_ADDRESS_2"
solana account $MINT_ADDRESS_2 --url https://api.devnet.solana.com
echo ""

echo "🔗 EXPLORER LINKS"
echo "================="
echo "Tree 1: https://explorer.solana.com/address/$TREE_ADDRESS_1?cluster=devnet"
echo "Tree 2: https://explorer.solana.com/address/$TREE_ADDRESS_2?cluster=devnet"
echo "Mint 1: https://explorer.solana.com/address/$MINT_ADDRESS_1?cluster=devnet"
echo "Mint 2: https://explorer.solana.com/address/$MINT_ADDRESS_2?cluster=devnet"
echo ""

echo "📊 RPC VERIFICATION"
echo "==================="

echo "Checking Tree Account Info via RPC..."
curl -X POST -H "Content-Type: application/json" -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 1,
    \"method\": \"getAccountInfo\",
    \"params\": [
        \"$TREE_ADDRESS_1\",
        {
            \"encoding\": \"base64\"
        }
    ]
}" https://api.devnet.solana.com

echo ""
echo ""

echo "Checking Mint Account Info via RPC..."
curl -X POST -H "Content-Type: application/json" -d "{
    \"jsonrpc\": \"2.0\",
    \"id\": 1,
    \"method\": \"getAccountInfo\",
    \"params\": [
        \"$MINT_ADDRESS_1\",
        {
            \"encoding\": \"base64\"
        }
    ]
}" https://api.devnet.solana.com

echo ""
echo ""

echo "✅ VERIFICATION COMPLETE"
echo "========================"
echo "Check the output above to verify:"
echo "1. Tree accounts exist on Solana devnet"
echo "2. Mint accounts exist on Solana devnet"
echo "3. All addresses are real (not simulated)"
echo ""
echo "📁 Migration Output Directory: migration_output/20250827_194737"
echo "📄 Database Records: Check SeiNFT and Tree models in Django admin"
echo ""
