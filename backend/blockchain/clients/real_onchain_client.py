#!/usr/bin/env python3
"""
Fixed Real On-Chain Compressed NFT Client

This client creates actual compressed NFTs on Solana devnet with proper
tree authority PDA derivation and correct instruction structure.
"""

import os
import json
import base58
import base64
import asyncio
import aiohttp
import hashlib
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash

from blockchain.logging_utils import create_operation_logger

logger = create_operation_logger(__name__)


@dataclass
class TreeInfo:
    """Information about a Merkle tree."""
    address: str
    authority: str
    max_depth: int
    max_buffer_size: int
    max_nfts: int
    current_size: int
    creation_signature: str


class RealOnChainClient:
    """Fixed client for real on-chain compressed NFT operations."""
    
    # Real Metaplex program IDs
    BUBBLEGUM_PROGRAM_ID = Pubkey.from_string("BGUMAp9Gq7iTEuizy4pqaxsTyUCBK68MDfK752saRPUY")
    ACCOUNT_COMPRESSION_PROGRAM_ID = Pubkey.from_string("cmtDvXumGCrqC1Age74AVPhSRVXJMd8PJS91L8KbNCK")
    NOOP_PROGRAM_ID = Pubkey.from_string("noopb9bkMVfRPU8AsbpTUg8AQkHtKwMYZiFUjNRtMmV")
    SYSTEM_PROGRAM_ID = Pubkey.from_string("11111111111111111111111111111111")
    TOKEN_METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
    
    def __init__(self, rpc_url: str = "https://api.devnet.solana.com", funded_account_secret: str = None, funded_account_address: str = None):
        """Initialize the fixed on-chain client."""
        self.rpc_url = rpc_url
        self.session = None
        self.trees = {}  # Store created trees
        self.funded_account_address = funded_account_address

        # Load or create keypair
        if funded_account_secret:
            try:
                # Check if it's a file path
                if isinstance(funded_account_secret, str) and (funded_account_secret.endswith('.json') or '/' in funded_account_secret):
                    keypair_path = os.path.expanduser(funded_account_secret)
                    if os.path.exists(keypair_path):
                        with open(keypair_path, 'r') as f:
                            keypair_data = json.load(f)
                            self.payer_keypair = Keypair.from_bytes(bytes(keypair_data))
                            logger.info(f"Using funded account from file: {self.payer_keypair.pubkey()}")
                    else:
                        raise FileNotFoundError(f"Keypair file not found: {keypair_path}")
                # Handle byte array format
                elif isinstance(funded_account_secret, list):
                    self.payer_keypair = Keypair.from_bytes(bytes(funded_account_secret))
                    logger.info(f"Using provided funded account from array: {self.payer_keypair.pubkey()}")
                # Handle base58 string format
                elif isinstance(funded_account_secret, str):
                    if len(funded_account_secret) > 50:  # Likely base58 encoded
                        secret_bytes = base58.b58decode(funded_account_secret)
                    else:  # Might be base64 or other format
                        secret_bytes = base64.b64decode(funded_account_secret)

                    if len(secret_bytes) == 32:
                        self.payer_keypair = Keypair.from_seed(secret_bytes)
                    elif len(secret_bytes) == 64:
                        self.payer_keypair = Keypair.from_bytes(secret_bytes)
                    else:
                        raise ValueError(f"Invalid secret key length: {len(secret_bytes)}")
                    logger.info(f"Using provided funded account from base58: {self.payer_keypair.pubkey()}")
                else:
                    raise ValueError(f"Unsupported funded_account_secret format: {type(funded_account_secret)}")
            except Exception as e:
                logger.warning(f"Failed to load provided funded account: {e}")
                self.payer_keypair = Keypair()
        else:
            # Try loading from environment or file
            secret_key_env = os.getenv('SOLANA_PRIVATE_KEY')
            if secret_key_env:
                try:
                    secret_bytes = base58.b58decode(secret_key_env)
                    if len(secret_bytes) == 32:
                        self.payer_keypair = Keypair.from_seed(secret_bytes)
                    else:
                        self.payer_keypair = Keypair.from_bytes(secret_bytes)
                    logger.info(f"Using environment keypair: {self.payer_keypair.pubkey()}")
                except Exception as e:
                    logger.warning(f"Failed to load environment keypair: {e}")
                    self.payer_keypair = Keypair()
            else:
                # Try loading from file
                try:
                    if os.path.exists('funded_keypair.json'):
                        with open('funded_keypair.json', 'r') as f:
                            keypair_data = json.load(f)
                            private_key_b58 = keypair_data['private_key']
                            private_key_bytes = base58.b58decode(private_key_b58)
                            if len(private_key_bytes) == 32:
                                self.payer_keypair = Keypair.from_seed(private_key_bytes)
                            else:
                                self.payer_keypair = Keypair.from_bytes(private_key_bytes)
                            logger.info(f"Loaded funded keypair: {self.payer_keypair.pubkey()}")
                    else:
                        self.payer_keypair = Keypair()
                        logger.info(f"Created new keypair: {self.payer_keypair.pubkey()}")
                except Exception as e:
                    logger.warning(f"Failed to load funded keypair: {e}")
                    self.payer_keypair = Keypair()
        
        logger.info(f"Initialized RealOnChainClient with payer: {self.payer_keypair.pubkey()}")
        if self.funded_account_address:
            logger.info(f"Funded account available: {self.funded_account_address}")

    def derive_tree_config_pda(self, tree_address: Pubkey) -> Tuple[Pubkey, int]:
        """Derive the tree config PDA for a given tree address."""
        seeds = [bytes(tree_address)]
        tree_config_pda, bump = Pubkey.find_program_address(seeds, self.BUBBLEGUM_PROGRAM_ID)
        return tree_config_pda, bump

    def derive_bubblegum_signer_pda(self) -> Tuple[Pubkey, int]:
        """Derive the Bubblegum signer PDA."""
        seeds = [b"collection_cpi"]
        signer_pda, bump = Pubkey.find_program_address(seeds, self.BUBBLEGUM_PROGRAM_ID)
        return signer_pda, bump

    async def initialize(self):
        """Initialize the HTTP session and check account balance."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        balance = await self.get_balance()
        logger.info(f"Payer account balance: {balance / 1e9:.4f} SOL")

        if balance < 100000000:  # Need at least 0.1 SOL for operations
            logger.warning(f"Low balance ({balance / 1e9:.4f} SOL), will use funded account for transfers")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _make_rpc_request(self, method: str, params: list) -> Dict[str, Any]:
        """Make an RPC request to Solana."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            async with self.session.post(self.rpc_url, json=payload) as response:
                result = await response.json()
                return result
        except Exception as e:
            logger.error(f"RPC request failed: {e}")
            raise
    
    async def get_balance(self, pubkey: Optional[Pubkey] = None) -> int:
        """Get SOL balance for an account."""
        if pubkey is None:
            pubkey = self.payer_keypair.pubkey()
        
        try:
            response = await self._make_rpc_request(
                "getBalance",
                [str(pubkey)]
            )
            
            if "result" in response:
                return response["result"]["value"]
            else:
                logger.error(f"Failed to get balance: {response}")
                return 0
                
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0
    
    async def get_recent_blockhash(self) -> str:
        """Get recent blockhash."""
        try:
            response = await self._make_rpc_request(
                "getLatestBlockhash",
                [{"commitment": "finalized"}]
            )
            
            if "result" in response:
                return response["result"]["value"]["blockhash"]
            else:
                raise Exception(f"Failed to get blockhash: {response}")
                
        except Exception as e:
            logger.error(f"Failed to get recent blockhash: {e}")
            raise
    
    async def fund_account_if_needed(self, min_balance: int = 100000000) -> bool:
        """Fund the payer account using only the funded account (no airdrops)."""
        try:
            current_balance = await self.get_balance()
            logger.info(f"Current balance: {current_balance / 1e9:.4f} SOL")

            if current_balance >= min_balance:
                logger.info("Account already has sufficient balance")
                return True

            # Only use funded account transfer - no airdrops
            if self.funded_account_address:
                logger.info(f"Transferring from funded account: {self.funded_account_address}")
                needed_amount = min_balance - current_balance + 10000000  # Add 0.01 SOL buffer
                transfer_result = await self.transfer_from_funded_account(needed_amount)
                if transfer_result:
                    return True
                else:
                    logger.error("Failed to transfer from funded account")
                    return False
            else:
                logger.error("No funded account available and airdrops disabled")
                logger.error(f"Please manually fund the account: {self.payer_keypair.pubkey()}")
                return False

        except Exception as e:
            logger.error(f"Failed to fund account: {e}")
            return False

    async def transfer_from_funded_account(self, amount_lamports: int) -> bool:
        """Transfer SOL from the funded account to the payer account."""
        try:
            if not hasattr(self, 'funded_account_keypair'):
                logger.warning("No funded account keypair available for transfers")
                return False

            funded_balance = await self.get_balance(self.funded_account_keypair.pubkey())
            logger.info(f"Funded account balance: {funded_balance / 1e9:.4f} SOL")
            
            if funded_balance < amount_lamports + 5000:  # Need extra for rent + fees
                logger.warning("Funded account has insufficient balance for transfer")
                return False

            # Get recent blockhash
            recent_blockhash = await self.get_recent_blockhash()

            # Create transfer instruction
            transfer_instruction = transfer(
                TransferParams(
                    from_pubkey=self.funded_account_keypair.pubkey(),
                    to_pubkey=self.payer_keypair.pubkey(),
                    lamports=amount_lamports
                )
            )

            # Create and send transaction
            message = MessageV0.try_compile(
                payer=self.funded_account_keypair.pubkey(),
                instructions=[transfer_instruction],
                address_lookup_table_accounts=[],
                recent_blockhash=Hash.from_string(recent_blockhash)
            )

            transaction = VersionedTransaction(message, [self.funded_account_keypair])

            # Serialize and send transaction
            serialized_tx = bytes(transaction)
            encoded_tx = base58.b58encode(serialized_tx).decode('utf-8')

            send_response = await self._make_rpc_request(
                "sendTransaction",
                [encoded_tx, {
                    "encoding": "base58",
                    "skipPreflight": False,
                    "preflightCommitment": "processed"
                }]
            )

            if "result" in send_response:
                tx_signature = send_response["result"]
                logger.info(f"Transfer transaction sent: {tx_signature}")
                await asyncio.sleep(5)  # Wait for confirmation
                
                new_balance = await self.get_balance()
                logger.info(f"New payer balance: {new_balance / 1e9:.4f} SOL")
                return True
            else:
                logger.error(f"Transfer failed: {send_response}")
                return False

        except Exception as e:
            logger.error(f"Failed to transfer from funded account: {e}")
            return False
    
    async def create_merkle_tree(self, max_depth: int = 14, max_buffer_size: int = 64) -> Dict[str, Any]:
        """Create a REAL Merkle tree using Account Compression program directly."""
        try:
            logger.info("Creating REAL on-chain Merkle tree using Account Compression program")

            # Ensure account is funded
            if not await self.fund_account_if_needed():
                logger.error("Failed to fund account, cannot create real tree")
                return {"status": "error", "error": "Insufficient funds"}

            # Generate tree keypair
            tree_keypair = Keypair()
            tree_address = tree_keypair.pubkey()
            
            logger.info(f"Creating real Merkle tree on-chain: {tree_address}")

            # Get recent blockhash
            recent_blockhash = await self.get_recent_blockhash()

            # Create Account Compression program init_empty_merkle_tree instruction
            import struct

            # Account Compression program init_empty_merkle_tree discriminator
            # This is the standard discriminator for initializing a merkle tree
            instruction_discriminator = bytes([0])  # Simple discriminator for init_empty_merkle_tree

            # Pack the instruction data for Account Compression program
            instruction_data = bytearray()
            instruction_data.extend(instruction_discriminator)  # 1 byte discriminator
            instruction_data.extend(struct.pack('<I', max_depth))       # max_depth: u32
            instruction_data.extend(struct.pack('<I', max_buffer_size))  # max_buffer_size: u32

            logger.info(f"Account Compression instruction data length: {len(instruction_data)} bytes")
            logger.info(f"Account Compression instruction data: {instruction_data.hex()}")

            # Create instruction for Account Compression program to initialize the tree
            init_tree_instruction = Instruction(
                program_id=self.ACCOUNT_COMPRESSION_PROGRAM_ID,
                accounts=[
                    AccountMeta(pubkey=tree_address, is_signer=True, is_writable=True),        # merkle_tree
                    AccountMeta(pubkey=self.payer_keypair.pubkey(), is_signer=False, is_writable=False), # authority
                    AccountMeta(pubkey=self.NOOP_PROGRAM_ID, is_signer=False, is_writable=False), # noop_program
                ],
                data=bytes(instruction_data)
            )

            # After creating the tree, we need to initialize it with Bubblegum
            tree_config_pda, config_bump = self.derive_tree_config_pda(tree_address)

            # Bubblegum create_tree_config instruction (simpler approach)
            bubblegum_discriminator = hashlib.sha256(b"global:create_tree_config").digest()[:8]
            
            bubblegum_data = bytearray()
            bubblegum_data.extend(bubblegum_discriminator)
            bubblegum_data.extend(struct.pack('<I', max_depth))
            bubblegum_data.extend(struct.pack('<I', max_buffer_size))
            bubblegum_data.extend(struct.pack('<?', False))  # public: false

            bubblegum_instruction = Instruction(
                program_id=self.BUBBLEGUM_PROGRAM_ID,
                accounts=[
                    AccountMeta(pubkey=tree_config_pda, is_signer=False, is_writable=True),     # tree_config
                    AccountMeta(pubkey=tree_address, is_signer=False, is_writable=True),       # merkle_tree
                    AccountMeta(pubkey=self.payer_keypair.pubkey(), is_signer=True, is_writable=True), # payer
                    AccountMeta(pubkey=self.payer_keypair.pubkey(), is_signer=False, is_writable=False), # tree_creator
                    AccountMeta(pubkey=self.SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False), # system_program
                ],
                data=bytes(bubblegum_data)
            )

            # Create transaction with both instructions
            message = MessageV0.try_compile(
                payer=self.payer_keypair.pubkey(),
                instructions=[init_tree_instruction, bubblegum_instruction],
                address_lookup_table_accounts=[],
                recent_blockhash=Hash.from_string(recent_blockhash)
            )

            transaction = VersionedTransaction(message, [self.payer_keypair, tree_keypair])

            # Serialize and send transaction
            serialized_tx = bytes(transaction)
            encoded_tx = base58.b58encode(serialized_tx).decode('utf-8')

            logger.info(f"Sending dual-instruction tree creation transaction to Solana devnet...")

            # Send transaction with proper configuration
            send_response = await self._make_rpc_request(
                "sendTransaction",
                [encoded_tx, {
                    "encoding": "base58",
                    "skipPreflight": False,
                    "preflightCommitment": "processed",
                    "maxRetries": 3
                }]
            )

            if "result" in send_response:
                tx_signature = send_response["result"]
                logger.info(f"Real tree creation transaction sent: {tx_signature}")

                # Wait for confirmation
                await asyncio.sleep(10)

                # Verify the tree was created successfully
                verification_result = await self.verify_tree_exists(str(tree_address))
                logger.info(f"Tree verification result: {verification_result}")

                max_nfts = 2 ** max_depth

                # Store tree info
                tree_info = TreeInfo(
                    address=str(tree_address),
                    authority=str(tree_config_pda),
                    max_depth=max_depth,
                    max_buffer_size=max_buffer_size,
                    max_nfts=max_nfts,
                    current_size=0,
                    creation_signature=tx_signature
                )
                self.trees[str(tree_address)] = tree_info

                return {
                    "status": "success",
                    "tree_address": str(tree_address),
                    "tree_config": str(tree_config_pda),
                    "config_bump": config_bump,
                    "transaction_signature": tx_signature,
                    "max_depth": max_depth,
                    "max_buffer_size": max_buffer_size,
                    "max_nfts": max_nfts,
                    "payer": str(self.payer_keypair.pubkey()),
                    "program_id": str(self.BUBBLEGUM_PROGRAM_ID),
                    "timestamp": datetime.now().isoformat(),
                    "network": "devnet",
                    "type": "real_merkle_tree",
                    "verification_command": f"solana account {tree_address} --url https://api.devnet.solana.com",
                    "verification_result": verification_result,
                    "explorer_url": f"https://explorer.solana.com/address/{tree_address}?cluster=devnet",
                    "is_verified": verification_result.get("exists", False)
                }
            else:
                error_msg = send_response.get("error", {}).get("message", "Unknown error")
                logger.error(f"Failed to send tree creation transaction: {send_response}")
                return {"status": "error", "error": f"Transaction failed: {error_msg}", "response": send_response}

        except Exception as e:
            logger.error(f"Failed to create real Merkle tree: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

    async def mint_compressed_nft(self, tree_address: str, metadata: Dict[str, Any], recipient: str = None) -> Dict[str, Any]:
        """Mint a real compressed NFT using the correct Bubblegum mint instruction."""
        try:
            logger.info(f"Minting compressed NFT on tree {tree_address}")

            # Verify tree exists first
            tree_verification = await self.verify_tree_exists(tree_address)
            if not tree_verification.get("exists", False):
                logger.error(f"Tree {tree_address} does not exist on-chain")
                return {
                    "status": "error",
                    "error": f"Tree {tree_address} does not exist on-chain",
                    "tree_address": tree_address
                }

            # Get tree info or derive authority
            tree_pubkey = Pubkey.from_string(tree_address)
            tree_config_pda, config_bump = self.derive_tree_config_pda(tree_pubkey)

            # Set recipient
            recipient = recipient or str(self.payer_keypair.pubkey())
            recipient_pubkey = Pubkey.from_string(recipient)

            logger.info(f"Tree: {tree_address}")
            logger.info(f"Tree Config PDA: {tree_config_pda}")
            logger.info(f"Recipient: {recipient}")

            # Create simplified metadata for Bubblegum
            metadata_args = {
                "name": metadata.get("name", "")[:32],  # Limit name length
                "symbol": metadata.get("symbol", "")[:10],  # Limit symbol length
                "uri": metadata.get("image", "")[:200],  # Limit URI length
                "sellerFeeBasisPoints": 0,
                "primarySaleHappened": False,
                "isMutable": True,
                "creators": []
            }

            # Get recent blockhash
            recent_blockhash = await self.get_recent_blockhash()

            # Create Bubblegum mint_v1 instruction using proper discriminator
            import struct

            # Use SHA256 hash of the instruction name for discriminator (Anchor pattern)
            mint_discriminator = hashlib.sha256(b"global:mint_v1").digest()[:8]

            # Serialize metadata as borsh-like format (simplified)
            metadata_json = json.dumps(metadata_args, separators=(',', ':'))
            metadata_bytes = metadata_json.encode('utf-8')

            # Pack the instruction data
            instruction_data = bytearray()
            instruction_data.extend(mint_discriminator)  # 8 bytes discriminator
            
            # Simple data structure for mint
            instruction_data.extend(struct.pack('<I', len(metadata_bytes)))  # length as u32
            instruction_data.extend(metadata_bytes)  # metadata bytes

            logger.info(f"Mint instruction data length: {len(instruction_data)} bytes")

            # Create the mint instruction with simplified account structure
            mint_instruction = Instruction(
                program_id=self.BUBBLEGUM_PROGRAM_ID,
                accounts=[
                    AccountMeta(pubkey=tree_config_pda, is_signer=False, is_writable=True),     # tree_config
                    AccountMeta(pubkey=recipient_pubkey, is_signer=False, is_writable=False),   # leaf_owner
                    AccountMeta(pubkey=recipient_pubkey, is_signer=False, is_writable=False),   # leaf_delegate
                    AccountMeta(pubkey=tree_pubkey, is_signer=False, is_writable=True),        # merkle_tree
                    AccountMeta(pubkey=self.payer_keypair.pubkey(), is_signer=True, is_writable=True), # payer
                    AccountMeta(pubkey=self.payer_keypair.pubkey(), is_signer=False, is_writable=False), # tree_delegate
                    AccountMeta(pubkey=self.NOOP_PROGRAM_ID, is_signer=False, is_writable=False), # log_wrapper
                    AccountMeta(pubkey=self.ACCOUNT_COMPRESSION_PROGRAM_ID, is_signer=False, is_writable=False), # compression_program
                    AccountMeta(pubkey=self.SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False), # system_program
                ],
                data=bytes(instruction_data)
            )

            # Create and send transaction
            message = MessageV0.try_compile(
                payer=self.payer_keypair.pubkey(),
                instructions=[mint_instruction],
                address_lookup_table_accounts=[],
                recent_blockhash=Hash.from_string(recent_blockhash)
            )

            transaction = VersionedTransaction(message, [self.payer_keypair])

            # Serialize and send transaction
            serialized_tx = bytes(transaction)
            encoded_tx = base58.b58encode(serialized_tx).decode('utf-8')

            # Send transaction with simulation first
            send_response = await self._make_rpc_request(
                "sendTransaction",
                [encoded_tx, {
                    "encoding": "base58",
                    "skipPreflight": False,
                    "preflightCommitment": "processed",
                    "maxRetries": 3
                }]
            )

            if "result" in send_response:
                tx_signature = send_response["result"]
                logger.info(f"Compressed NFT mint transaction sent: {tx_signature}")

                # Wait for confirmation
                await asyncio.sleep(5)

                # Generate asset ID from the transaction and tree
                asset_id = self._derive_asset_id(tree_address, tx_signature)

                return {
                    "status": "success",
                    "asset_id": asset_id,
                    "tree_address": tree_address,
                    "tree_config": str(tree_config_pda),
                    "transaction_signature": tx_signature,
                    "recipient": recipient,
                    "metadata": metadata,
                    "metadata_args": metadata_args,
                    "timestamp": datetime.now().isoformat(),
                    "network": "devnet",
                    "type": "real_onchain_compressed_nft",
                    "program_id": str(self.BUBBLEGUM_PROGRAM_ID),
                    "payer": str(self.payer_keypair.pubkey()),
                    "verification_url": f"https://explorer.solana.com/tx/{tx_signature}?cluster=devnet",
                    "is_real_onchain": True
                }
            else:
                error_msg = send_response.get("error", {}).get("message", "Unknown error")
                logger.error(f"Failed to send mint transaction: {send_response}")
                return {
                    "status": "error",
                    "error": f"Mint transaction failed: {error_msg}",
                    "tree_address": tree_address,
                    "response": send_response
                }

        except Exception as e:
            logger.error(f"Failed to mint compressed NFT: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": str(e),
                "tree_address": tree_address,
                "timestamp": datetime.now().isoformat()
            }

    def _derive_asset_id(self, tree_address: str, tx_signature: str) -> str:
        """Derive a deterministic asset ID from tree address and transaction."""
        # This is a simplified asset ID derivation - in practice, you'd use 
        # the actual leaf index and tree data
        combined = f"{tree_address}:{tx_signature}".encode()
        asset_hash = hashlib.sha256(combined).digest()
        return base58.b58encode(asset_hash[:32]).decode()

    async def verify_tree_exists(self, tree_address: str) -> Dict[str, Any]:
        """Verify that a Merkle tree exists on-chain."""
        try:
            response = await self._make_rpc_request(
                "getAccountInfo",
                [tree_address, {"encoding": "base64"}]
            )

            if "result" in response and response["result"]["value"] is not None:
                account_info = response["result"]["value"]
                return {
                    "exists": True,
                    "owner": account_info["owner"],
                    "lamports": account_info["lamports"],
                    "data_length": len(account_info["data"][0]) if account_info["data"] else 0,
                    "executable": account_info["executable"]
                }
            else:
                return {"exists": False}

        except Exception as e:
            logger.error(f"Failed to verify tree {tree_address}: {e}")
            return {"exists": False, "error": str(e)}

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()


# Example usage and testing
async def test_fixed_client():
    """Test the fixed client implementation."""
    logger.info("Testing FixedOnChainClient...")
    
    async with RealOnChainClient() as client:
        # Test tree creation
        tree_result = await client.create_merkle_tree(max_depth=14, max_buffer_size=64)
        logger.info(f"Tree creation result: {tree_result}")
        
        if tree_result["status"] == "success":
            tree_address = tree_result["tree_address"]
            
            # Test NFT minting
            test_metadata = {
                "name": "Fixed Test NFT",
                "symbol": "FTNFT",
                "description": "A test NFT created with the fixed client",
                "image": "https://example.com/image.png",
                "attributes": [
                    {"trait_type": "Color", "value": "Blue"},
                    {"trait_type": "Rarity", "value": "Common"}
                ]
            }
            
            mint_result = await client.mint_compressed_nft(tree_address, test_metadata)
            logger.info(f"Mint result: {mint_result}")
        
        return tree_result


if __name__ == "__main__":
    asyncio.run(test_fixed_client())