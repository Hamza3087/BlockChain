"""
Django management command to deploy Metaplex Bubblegum program.
"""

import asyncio
import json
from django.core.management.base import BaseCommand, CommandError
from blockchain.scripts import deploy_bubblegum


class Command(BaseCommand):
    help = 'Deploy Metaplex Bubblegum program on Solana devnet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--network',
            type=str,
            default='devnet',
            help='Solana network to deploy to (devnet, testnet, mainnet)',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify existing deployment without deploying',
        )

    def handle(self, *args, **options):
        network = options['network']
        verify_only = options['verify_only']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting Bubblegum deployment on {network}...')
        )
        
        try:
            # Run the deployment
            result = asyncio.run(deploy_bubblegum())
            
            # Display results
            self.stdout.write(
                self.style.SUCCESS('\n=== Deployment Results ===')
            )
            self.stdout.write(json.dumps(result, indent=2))
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Bubblegum deployment successful on {network}!'
                    )
                )
                self.stdout.write(
                    f"Program ID: {result['program_id']}"
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'\n❌ Deployment failed: {result["message"]}'
                    )
                )
                raise CommandError(f"Deployment failed: {result['message']}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Deployment error: {str(e)}')
            )
            raise CommandError(f"Deployment error: {str(e)}")
