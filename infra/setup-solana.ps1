# Solana CLI Setup Script for ReplantWorld
# This script configures Solana CLI for development

Write-Host "Setting up Solana CLI for ReplantWorld development..." -ForegroundColor Green

# Check if Solana CLI is installed
try {
    $solanaVersion = solana --version
    Write-Host "Solana CLI found: $solanaVersion" -ForegroundColor Green
} catch {
    Write-Host "Solana CLI not found. Please install it first:" -ForegroundColor Red
    Write-Host "Run: sh -c `"$(curl -sSfL https://release.solana.com/stable/install)`"" -ForegroundColor Yellow
    exit 1
}

# Configure Solana CLI to use devnet
Write-Host "Configuring Solana CLI to use devnet..." -ForegroundColor Yellow
solana config set --url https://api.devnet.solana.com

# Generate a new keypair if one doesn't exist
$keypairPath = "$env:USERPROFILE\.config\solana\id.json"
if (-not (Test-Path $keypairPath)) {
    Write-Host "Generating new Solana keypair..." -ForegroundColor Yellow
    solana-keygen new --outfile $keypairPath --no-bip39-passphrase
} else {
    Write-Host "Keypair already exists at: $keypairPath" -ForegroundColor Green
}

# Get the public key
$publicKey = solana-keygen pubkey $keypairPath
Write-Host "Wallet Public Key: $publicKey" -ForegroundColor Cyan

# Request airdrop
Write-Host "Requesting SOL airdrop..." -ForegroundColor Yellow
try {
    solana airdrop 2 $publicKey
    Start-Sleep -Seconds 5
    
    # Check balance
    $balance = solana balance $publicKey
    Write-Host "Current balance: $balance" -ForegroundColor Green
    
    # Save wallet info to file
    $walletInfo = @{
        publicKey = $publicKey
        balance = $balance
        network = "devnet"
        timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    
    $walletInfo | ConvertTo-Json | Out-File -FilePath "wallet-info.json" -Encoding UTF8
    Write-Host "Wallet information saved to wallet-info.json" -ForegroundColor Green
    
} catch {
    Write-Host "Failed to request airdrop. This might be due to rate limiting." -ForegroundColor Red
    Write-Host "You can try again later or use the Solana faucet: https://faucet.solana.com/" -ForegroundColor Yellow
}

# Display configuration
Write-Host "`nSolana Configuration:" -ForegroundColor Cyan
solana config get

Write-Host "`nSolana CLI setup completed!" -ForegroundColor Green
Write-Host "Public Key: $publicKey" -ForegroundColor Cyan
Write-Host "Network: devnet" -ForegroundColor Cyan
