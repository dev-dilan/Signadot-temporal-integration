import os
import asyncio
import uuid
from temporalio.client import Client, Interceptor, OutboundInterceptor
from temporalio.client import StartWorkflowInput
from temporalio.api.common.v1 import Payload
from models import PaymentDetails # Ensure models.py is accessible
from baggage import Baggage

class HeaderInterceptor(Interceptor):
    def __init__(self, headers: dict):
        self.headers = headers
    
    def intercept_client(self, next: OutboundInterceptor) -> OutboundInterceptor:
        return HeaderOutboundInterceptor(next, self.headers)

class HeaderOutboundInterceptor(OutboundInterceptor):
    def __init__(self, next: OutboundInterceptor, headers: dict):
        super().__init__(next)
        self.headers = headers
    
    async def start_workflow(self, input: StartWorkflowInput) -> str:
        # Add our headers to the workflow
        if self.headers:
            for key, value in self.headers.items():
                if isinstance(value, str):
                    # Headers must be Payload objects
                    print(f"{value.encode('utf-8')} is utf 8 encodeing of original {value}")
                    input.headers[key] = Payload(data=value.encode('utf-8'))
        
        # Continue with the workflow start
        return await self.next.start_workflow(input)

async def start_workflow_with_routing(payment_details: PaymentDetails, routing_key: str = None):
    """
    Starts the MoneyTransferWorkflow with optional routing.
    """
    temporal_server_url = os.getenv("TEMPORAL_SERVER_URL", "temporal-server:7233")
    task_queue = os.getenv("TASK_QUEUE", "money-transfer")
    
    # Prepare headers
    headers = {} # Corrected variable name from headers_dict to headers
    if routing_key:
        headers["baggage"] = routing_key

    client = await Client.connect(temporal_server_url, interceptors=[HeaderInterceptor(headers)] if headers else [])    

    workflow_id = f"money-transfer-{uuid.uuid4()}"

    handle = await client.start_workflow(
        "MoneyTransferWorkflow",
        payment_details,
        id=workflow_id,
        task_queue=task_queue
    )
    
    result_message = f"Started workflow with ID: {handle.id}, Run ID: {handle.result_run_id}, Routing Key: {Baggage().extract_routing_key_from_baggage(headers) or 'None (baseline)'}"
    print(result_message)
    return {
        "message": result_message,
        "workflow_id": handle.id,
        "run_id": handle.result_run_id,
        "routing_key_used": routing_key or "baseline"
    }
