#!/usr/bin/env python3
"""
Deploy Metaplex Bubblegum program on Solana devnet.

This script handles the deployment of the Metaplex Bubblegum program
for compressed NFT functionality on Solana devnet.
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import structlog
from solders.pubkey import Pubkey

# Add the parent directory to the path so we can import from blockchain
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from blockchain.services import get_solana_service
    from blockchain.config import get_solana_config, get_bubblegum_program_id
except ImportError:
    print("Warning: Could not import blockchain modules. Running in standalone mode.")

    def get_solana_config():
        return {
            'network': os.getenv('SOLANA_NETWORK', 'devnet'),
            'keypair_path': os.getenv('SOLANA_KEYPAIR_PATH', '~/.config/solana/id.json')
        }

    def get_bubblegum_program_id(network):
        return 'BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY'

logger = structlog.get_logger(__name__)


class BubblegumDeployer:
    """Handles deployment of Metaplex Bubblegum program."""

    def __init__(self):
        self.config = get_solana_config()
        self.network = self.config['network']
        self.keypair_path = os.path.expanduser(self.config['keypair_path'])

    def check_solana_cli(self) -> bool:
        """Check if Solana CLI is installed and configured."""
        try:
            result = subprocess.run(['solana', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("Solana CLI found", version=result.stdout.strip())
                return True
            else:
                logger.error("Solana CLI not found or not working")
                return False
        except FileNotFoundError:
            logger.error("Solana CLI not installed")
            return False

    def check_keypair(self) -> bool:
        """Check if keypair exists and is valid."""
        if not os.path.exists(self.keypair_path):
            logger.error("Keypair not found", path=self.keypair_path)
            return False

        try:
            with open(self.keypair_path, 'r') as f:
                keypair_data = json.load(f)

            # Validate keypair format
            if isinstance(keypair_data, list) and len(keypair_data) == 64:
                logger.info("Valid keypair found", path=self.keypair_path)
                return True
            else:
                logger.error("Invalid keypair format", path=self.keypair_path)
                return False

        except Exception as e:
            logger.error("Failed to read keypair", path=self.keypair_path, error=str(e))
            return False

    def get_wallet_balance(self) -> Optional[float]:
        """Get current wallet balance."""
        try:
            result = subprocess.run(
                ['solana', 'balance', '--keypair', self.keypair_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                balance_str = result.stdout.strip().split()[0]
                balance = float(balance_str)
                logger.info("Wallet balance", balance=balance, unit="SOL")
                return balance
            else:
                logger.error("Failed to get balance", error=result.stderr)
                return None

        except Exception as e:
            logger.error("Error getting wallet balance", error=str(e))
            return None

    def ensure_sufficient_balance(self, required_sol: float = 2.0) -> bool:
        """Ensure wallet has sufficient balance for deployment."""
        balance = self.get_wallet_balance()

        if balance is None:
            return False

        if balance < required_sol:
            logger.warning(
                "Insufficient balance for deployment",
                current=balance,
                required=required_sol
            )

            # Try to request airdrop on devnet
            if self.network == 'devnet':
                logger.info("Requesting SOL airdrop on devnet")
                try:
                    result = subprocess.run(
                        ['solana', 'airdrop', '2', '--keypair', self.keypair_path],
                        capture_output=True,
                        text=True
                    )

                    if result.returncode == 0:
                        logger.info("Airdrop successful")
                        # Check balance again
                        new_balance = self.get_wallet_balance()
                        return new_balance and new_balance >= required_sol
                    else:
                        logger.error("Airdrop failed", error=result.stderr)
                        return False

                except Exception as e:
                    logger.error("Error requesting airdrop", error=str(e))
                    return False
            else:
                logger.error("Insufficient balance and not on devnet - cannot request airdrop")
                return False

        return True

    def check_program_deployed(self) -> bool:
        """Check if Bubblegum program is already deployed."""
        program_id = get_bubblegum_program_id(self.network)

        try:
            result = subprocess.run(
                ['solana', 'account', program_id],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and 'Account not found' not in result.stdout:
                logger.info("Bubblegum program already deployed", program_id=program_id)
                return True
            else:
                logger.info("Checking program deployment status", program_id=program_id)
                return False

        except Exception as e:
            logger.error("Error checking program deployment", error=str(e))
            return False

    async def verify_deployment(self) -> bool:
        """Verify the deployment by testing RPC connection to the program."""
        try:
            # Try to use the service if available
            try:
                service = await get_solana_service()
                program_id = Pubkey.from_string(get_bubblegum_program_id(self.network))

                # Try to get program account info
                account_info = await service.client.get_account_info(program_id)

                if account_info.value is not None:
                    logger.info(
                        "Deployment verified - program account found",
                        program_id=str(program_id),
                        owner=str(account_info.value.owner) if account_info.value.owner else "None"
                    )
                    return True
                else:
                    logger.error("Deployment verification failed - program account not found")
                    return False
            except:
                # Fallback to CLI verification
                return self.check_program_deployed()

        except Exception as e:
            logger.error("Error verifying deployment", error=str(e))
            return False

    async def deploy(self) -> Dict[str, Any]:
        """Deploy the Metaplex Bubblegum program."""
        logger.info("Starting Metaplex Bubblegum deployment", network=self.network)

        deployment_result = {
            "success": False,
            "network": self.network,
            "program_id": get_bubblegum_program_id(self.network),
            "checks": {},
            "message": ""
        }

        # Pre-deployment checks
        logger.info("Running pre-deployment checks")

        # Check Solana CLI
        if not self.check_solana_cli():
            deployment_result["message"] = "Solana CLI not available"
            return deployment_result
        deployment_result["checks"]["solana_cli"] = True

        # Check keypair
        if not self.check_keypair():
            deployment_result["message"] = "Invalid or missing keypair"
            return deployment_result
        deployment_result["checks"]["keypair"] = True

        # Check balance
        if not self.ensure_sufficient_balance():
            deployment_result["message"] = "Insufficient SOL balance"
            return deployment_result
        deployment_result["checks"]["balance"] = True

        # Check if already deployed
        if self.check_program_deployed():
            deployment_result["success"] = True
            deployment_result["message"] = "Bubblegum program already deployed"
            deployment_result["checks"]["already_deployed"] = True

            # Verify deployment
            if await self.verify_deployment():
                deployment_result["checks"]["verification"] = True
                logger.info("Bubblegum deployment confirmed")
                return deployment_result

        # Note: Metaplex Bubblegum is pre-deployed on Solana networks
        logger.info("Metaplex Bubblegum is a pre-deployed program on Solana networks")
        deployment_result["success"] = True
        deployment_result["message"] = "Using pre-deployed Metaplex Bubblegum program"
        deployment_result["checks"]["pre_deployed"] = True

        # Verify we can access it
        if await self.verify_deployment():
            deployment_result["checks"]["verification"] = True
            logger.info("Successfully verified access to Bubblegum program")
        else:
            deployment_result["success"] = False
            deployment_result["message"] = "Cannot access Bubblegum program"

        return deployment_result


async def deploy_bubblegum():
    """Main deployment function."""
    deployer = BubblegumDeployer()
    result = await deployer.deploy()

    print(json.dumps(result, indent=2))

    if result["success"]:
        logger.info("Deployment completed successfully")
        return result
    else:
        logger.error("Deployment failed", message=result["message"])
        raise Exception(f"Deployment failed: {result['message']}")


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    try:
        result = asyncio.run(deploy_bubblegum())
        sys.exit(0)
    except Exception as e:
        logger.error("Deployment script failed", error=str(e))
        sys.exit(1)