"""
Django management command to create Merkle trees for compressed NFTs.
"""

import asyncio
import json
from django.core.management.base import BaseCommand, CommandError
from blockchain.services import get_solana_service
from blockchain.merkle_tree import MerkleTreeManager, MerkleTreeConfig


class Command(BaseCommand):
    help = 'Create a Merkle tree for compressed NFTs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-depth',
            type=int,
            default=14,
            help='Maximum tree depth (determines capacity: 2^depth)',
        )
        parser.add_argument(
            '--max-buffer-size',
            type=int,
            default=64,
            help='Maximum buffer size for concurrent operations',
        )
        parser.add_argument(
            '--canopy-depth',
            type=int,
            default=0,
            help='Canopy depth for on-chain proof storage',
        )
        parser.add_argument(
            '--tree-name',
            type=str,
            help='Optional name for the tree',
        )
        parser.add_argument(
            '--private',
            action='store_true',
            help='Create a private tree (default is public)',
        )
        parser.add_argument(
            '--save-to-file',
            type=str,
            help='Save tree information to specified file',
        )

    def handle(self, *args, **options):
        max_depth = options['max_depth']
        max_buffer_size = options['max_buffer_size']
        canopy_depth = options['canopy_depth']
        tree_name = options['tree_name']
        public = not options['private']
        save_file = options['save_to_file']
        
        self.stdout.write(
            self.style.SUCCESS(f'Creating Merkle tree with depth {max_depth}...')
        )
        
        try:
            # Run the tree creation
            result = asyncio.run(self._create_tree(
                max_depth, max_buffer_size, canopy_depth, tree_name, public, save_file
            ))
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS('\n=== Tree Creation Results ===')
            )
            self.stdout.write(f"Tree Address: {result.tree_address}")
            self.stdout.write(f"Tree Authority: {result.tree_authority}")
            self.stdout.write(f"Status: {result.status.value}")
            self.stdout.write(f"Max Capacity: {result.config.max_capacity:,} NFTs")
            self.stdout.write(f"Creation Signature: {result.creation_signature}")
            
            if result.metadata and result.metadata.get('name'):
                self.stdout.write(f"Tree Name: {result.metadata['name']}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Merkle tree created successfully!'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Tree creation failed: {str(e)}')
            )
            raise CommandError(f"Tree creation failed: {str(e)}")
    
    async def _create_tree(self, max_depth, max_buffer_size, canopy_depth, tree_name, public, save_file):
        """Create the Merkle tree asynchronously."""
        # Get Solana service
        service = await get_solana_service()
        if not service.client:
            raise Exception("Solana client not available")
        
        # Create tree manager
        tree_manager = MerkleTreeManager(service.client)
        
        # Create tree configuration
        config = tree_manager.create_tree_config(
            max_depth=max_depth,
            max_buffer_size=max_buffer_size,
            canopy_depth=canopy_depth,
            public=public
        )
        
        self.stdout.write(f"Estimated cost: {config.estimated_cost_lamports / 1_000_000_000:.6f} SOL")
        
        # Create the tree
        tree_info = await tree_manager.create_merkle_tree(
            config=config,
            tree_name=tree_name
        )

        # Save tree data to persistent storage for other commands to use
        tree_manager.save_trees_to_file('managed_trees.json')

        # Save to file if requested
        if save_file:
            tree_data = tree_info.to_dict()
            with open(save_file, 'w') as f:
                json.dump(tree_data, f, indent=2)
            self.stdout.write(f"Tree information saved to {save_file}")

        return tree_info
