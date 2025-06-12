import os
import asyncio
import uuid
from temporalio.client import Client
from models import PaymentDetails # Ensure models.py is accessible

async def start_workflow_with_routing(payment_details: PaymentDetails, routing_key: str = None):
    """
    Starts the MoneyTransferWorkflow with optional routing.
    """
    temporal_server_url = os.getenv("TEMPORAL_SERVER_URL", "temporal-server:7233")
    task_queue = os.getenv("TASK_QUEUE", "money-transfer")
    client = await Client.connect(temporal_server_url)

    # Prepare headers
    headers = {} # Corrected variable name from headers_dict to headers
    if routing_key:
        headers["sd-routing-key"] = routing_key

    workflow_id = f"money-transfer-{uuid.uuid4()}"

    handle = await client.start_workflow(
        "MoneyTransferWorkflow",
        payment_details,
        id=workflow_id,
        task_queue=task_queue,
        headers=headers
    )
    
    result_message = f"Started workflow with ID: {handle.id}, Run ID: {handle.result_run_id}, Routing Key: {routing_key or 'None (baseline)'}"
    print(result_message)
    return {
        "message": result_message,
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "routing_key_used": routing_key or "baseline"
    }

if __name__ == "__main__":
    # Example usage (optional, as the UI will trigger this)
    example_payment = PaymentDetails(
        from_account="acc_main_001",
        to_account="acc_main_002",
        amount="25.50",
        reference="Test from client.py main"
    )
    # Test with a routing key
    # asyncio.run(start_workflow_with_routing(payment_details=example_payment, routing_key="test-sandbox-key"))
    # Test for baseline
    asyncio.run(start_workflow_with_routing(payment_details=example_payment))
