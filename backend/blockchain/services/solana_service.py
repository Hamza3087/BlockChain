"""
Solana Service (mock for health check)
"""

class DummySolanaService:
    async def get_health_status(self):
        return {"status": "healthy", "message": "Connected (mock)"}

# Factory function
async def get_solana_service():
    return DummySolanaService()
