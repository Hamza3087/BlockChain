#!/bin/bash

# Solana CLI Setup Script for ReplantWorld
# This script configures Solana CLI for development

echo "Setting up Solana CLI for ReplantWorld development..."

# Check if Solana CLI is installed
if ! command -v solana &> /dev/null; then
    echo "Solana CLI not found. Installing..."
    sh -c "$(curl -sSfL https://release.solana.com/stable/install)"
    export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
else
    echo "Solana CLI found: $(solana --version)"
fi

# Configure Solana CLI to use devnet
echo "Configuring Solana CLI to use devnet..."
solana config set --url https://api.devnet.solana.com

# Generate a new keypair if one doesn't exist
KEYPAIR_PATH="$HOME/.config/solana/id.json"
if [ ! -f "$KEYPAIR_PATH" ]; then
    echo "Generating new Solana keypair..."
    solana-keygen new --outfile "$KEYPAIR_PATH" --no-bip39-passphrase
else
    echo "Keypair already exists at: $KEYPAIR_PATH"
fi

# Get the public key
PUBLIC_KEY=$(solana-keygen pubkey "$KEYPAIR_PATH")
echo "Wallet Public Key: $PUBLIC_KEY"

# Request airdrop
echo "Requesting SOL airdrop..."
if solana airdrop 2 "$PUBLIC_KEY"; then
    sleep 5
    
    # Check balance
    BALANCE=$(solana balance "$PUBLIC_KEY")
    echo "Current balance: $BALANCE"
    
    # Save wallet info to file
    cat > wallet-info.json << EOF
{
    "publicKey": "$PUBLIC_KEY",
    "balance": "$BALANCE",
    "network": "devnet",
    "timestamp": "$(date -u +"%Y-%m-%d %H:%M:%S")"
}
EOF
    echo "Wallet information saved to wallet-info.json"
    
else
    echo "Failed to request airdrop. This might be due to rate limiting."
    echo "You can try again later or use the Solana faucet: https://faucet.solana.com/"
fi

# Display configuration
echo ""
echo "Solana Configuration:"
solana config get

echo ""
echo "Solana CLI setup completed!"
echo "Public Key: $PUBLIC_KEY"
echo "Network: devnet"
