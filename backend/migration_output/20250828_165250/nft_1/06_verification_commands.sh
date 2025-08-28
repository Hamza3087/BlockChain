
# Verify transaction on Solana devnet
curl -X POST -H "Content-Type: application/json" -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getTransaction",
    "params": [
        "3M4pr3KDadRvQPDzY18CMDKQWeGiaVeFki57hRLoYFhD5f5SBC2uFDNnHa5VUCVE9LMbYHoEU79rsQoxYEmcHyYt",
        {
            "encoding": "json",
            "commitment": "confirmed",
            "maxSupportedTransactionVersion": 0
        }
    ]
}' https://api.devnet.solana.com

# Check transaction status
curl -X POST -H "Content-Type: application/json" -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getSignatureStatuses",
    "params": [
        ["3M4pr3KDadRvQPDzY18CMDKQWeGiaVeFki57hRLoYFhD5f5SBC2uFDNnHa5VUCVE9LMbYHoEU79rsQoxYEmcHyYt"]
    ]
}' https://api.devnet.solana.com

# View on Solana Explorer
echo "View on Solana Explorer: https://explorer.solana.com/tx/3M4pr3KDadRvQPDzY18CMDKQWeGiaVeFki57hRLoYFhD5f5SBC2uFDNnHa5VUCVE9LMbYHoEU79rsQoxYEmcHyYt?cluster=devnet"



# Verify Merkle Tree Account
echo "=== Verifying Merkle Tree Account ==="
solana account erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM --url https://api.devnet.solana.com

# Check tree account info via RPC
echo "=== Tree Account Info via RPC ==="
curl -X POST -H "Content-Type: application/json" -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "getAccountInfo",
    "params": [
        "erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM",
        {
            "encoding": "base64"
        }
    ]
}' https://api.devnet.solana.com

# View on Solana Explorer
echo "View Tree on Solana Explorer: https://explorer.solana.com/address/erY15sCGJmk3H7y9BLZRLmmLgY8P4We1nGUsgBL5kJM?cluster=devnet"
