import asyncio
import os
import sys
from platform_sdk import SandboxAwareWorker
from workflows import MoneyTransferWorkflow
from activities import BankingActivities

async def main():
    """Main entry point for the Temporal worker"""
    
    print("=" * 60)
    print("TEMPORAL MONEY TRANSFER WORKER - BASELINE VERSION")
    print("=" * 60)
    
    # Get configuration from environment variables
    task_queue = os.getenv("TASK_QUEUE", "money-transfer")
    sandbox_name = os.getenv("SANDBOX_NAME", "")
    
    print(f"Configuration:")
    print(f"  Task Queue: {task_queue}")
    print(f"  Sandbox Name: {sandbox_name or 'baseline'}")
    print(f"  Temporal Server: {os.getenv('TEMPORAL_SERVER_URL', 'temporal-server:7233')}")
    print(f"  Routes API: {os.getenv('ROUTES_API_URL', 'http://routes-api:8081')}")
    print()
    
    try:
        # Create banking activities instance
        banking_activities = BankingActivities()
        
        # Create the sandbox-aware worker using the platform SDK
        worker = SandboxAwareWorker(
            task_queue=task_queue,
            workflows=[MoneyTransferWorkflow],
            activities=[
                banking_activities.withdraw,
                banking_activities.deposit,
            ]
        )
        
        print("Starting worker... Press Ctrl+C to stop")
        print("=" * 60)
        
        # Run the worker (this will block)
        await worker.run()
        
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())