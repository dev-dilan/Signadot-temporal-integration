import os
import asyncio
import time # For monotonic time
import aiohttp
from typing import List, Any, Optional, Set # Ensure Set is imported
from urllib.parse import urlencode, urlunparse, urlparse, ParseResult # Ensure all are imported

from temporalio.worker import Worker, Interceptor
from temporalio.client import Client
from temporalio.worker._interceptor import (
    ExecuteActivityInput,
    ExecuteWorkflowInput,
    WorkflowInboundInterceptor, # Added
    ActivityInboundInterceptor, # Added
)
from temporalio.exceptions import ApplicationError # For non-retryable errors

# Default config values mirroring the JS example (can be overridden by env vars)
DEFAULT_ROUTE_SERVER_ADDR = "http://localhost" # Default address for the routing rules API
DEFAULT_BASELINE_KIND = "Deployment"
DEFAULT_BASELINE_NAMESPACE = "default"
DEFAULT_BASELINE_NAME = "location" # Placeholder, configure as needed
DEFAULT_REFRESH_INTERVAL = 5 # seconds

class RoutesAPIClient:
    """
    Client for Signadot's Routes API to fetch and evaluate routing keys
    based on /api/v1/workloads/routing-rules endpoint.
    """
    def __init__(self, sandbox_name: str):
        self.sandbox_name = sandbox_name # Current sandbox name, empty for baseline

        # Configuration from environment variables or defaults
        self.route_server_addr_base = os.getenv("ROUTES_API_ROUTE_SERVER_ADDR", DEFAULT_ROUTE_SERVER_ADDR)
        parsed_addr = urlparse(self.route_server_addr_base)
        self.route_server_scheme = parsed_addr.scheme or "http"
        self.route_server_netloc = parsed_addr.netloc
        
        self.baseline_kind = os.getenv("ROUTES_API_BASELINE_KIND", DEFAULT_BASELINE_KIND)
        self.baseline_namespace = os.getenv("ROUTES_API_BASELINE_NAMESPACE", DEFAULT_BASELINE_NAMESPACE)
        self.baseline_name = os.getenv("ROUTES_API_BASELINE_NAME", DEFAULT_BASELINE_NAME)
        
        self.refresh_interval = int(os.getenv("ROUTES_API_REFRESH_INTERVAL_SECONDS", str(DEFAULT_REFRESH_INTERVAL)))

        self._routing_keys_cache: Set[str] = set()
        self._cache_update_lock = asyncio.Lock() # Lock for initiating an update
        self._cache_updated_event = asyncio.Event() # Event to signal update completion
        self._last_successful_update_time: float = 0.0 # Using time.monotonic()
        self._is_first_update_done = False # Tracks if the first fetch attempt has completed

    def _build_routes_url(self) -> str:
        """Constructs the URL for the routing rules API."""
        query_params = {
            'baselineKind': self.baseline_kind,
            'baselineNamespace': self.baseline_namespace,
            'baselineName': self.baseline_name
        }
        if self.sandbox_name: # If this is a sandboxed workload, specify destinationSandboxName
            query_params['destinationSandboxName'] = self.sandbox_name
        
        path = '/api/v1/workloads/routing-rules'
        
        url_parts = ParseResult(
            scheme=self.route_server_scheme,
            netloc=self.route_server_netloc,
            path=path,
            params='',
            query=urlencode(query_params),
            fragment=''
        )
        return urlunparse(url_parts)

    async def _perform_fetch_and_update(self) -> None:
        """The actual fetching and cache update logic."""
        url = self._build_routes_url()
        print(f"RoutesAPIClient: Attempting to fetch routes from url={url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_routing_keys = set()
                        if isinstance(data, dict) and 'routingRules' in data and isinstance(data['routingRules'], list):
                            for rule in data['routingRules']:
                                if isinstance(rule, dict) and 'routingKey' in rule and rule['routingKey'] is not None:
                                    new_routing_keys.add(str(rule['routingKey']))
                        
                        self._routing_keys_cache = new_routing_keys
                        self._last_successful_update_time = time.monotonic()
                        self._is_first_update_done = True
                        print(f"RoutesAPIClient: Routing keys updated: {list(self._routing_keys_cache)}")
                    else:
                        print(f"RoutesAPIClient: Error fetching routes. Status: {response.status}, Body: {await response.text()}")
        except aiohttp.ClientError as e:
            print(f"RoutesAPIClient: HTTP client error fetching routes: {e}")
        except Exception as e:
            print(f"RoutesAPIClient: Error during route fetch/parse: {e}")

    async def _ensure_cache_fresh(self) -> None:
        """Ensures the cache is up-to-date based on the refresh interval."""
        current_time = time.monotonic()
        needs_update = not self._is_first_update_done or \
                       (current_time - self._last_successful_update_time > self.refresh_interval)

        if needs_update:
            if self._cache_update_lock.locked():
                print("RoutesAPIClient: Update in progress by another task, waiting...")
                await self._cache_updated_event.wait()
                print("RoutesAPIClient: Update completed by another task or wait timed out.")
            else:
                async with self._cache_update_lock:
                    current_time_after_lock = time.monotonic() # Re-check time after acquiring lock
                    if not self._is_first_update_done or \
                       (current_time_after_lock - self._last_successful_update_time > self.refresh_interval):
                        
                        self._cache_updated_event.clear()
                        try:
                            await self._perform_fetch_and_update()
                        finally:
                            self._cache_updated_event.set()
                            print("RoutesAPIClient: Cache update cycle finished, event set.")
                    else:
                        # Cache was updated by another task while this one was waiting for the lock
                        if not self._cache_updated_event.is_set(): self._cache_updated_event.set()


    async def should_process(self, routing_key: Optional[str]) -> bool:
        """
        Determines if the current worker should process a task with the given routing key.
        """
        await self._ensure_cache_fresh()
        current_cached_keys = self._routing_keys_cache

        if self.sandbox_name: # This is a sandboxed workload
            if routing_key is None:
                print(f"RoutesAPIClient (Sandbox: {self.sandbox_name}): Skipping task, no routing key provided.")
                return False
            
            should = routing_key in current_cached_keys
            log_action = "Processing" if should else "Skipping"
            print(f"RoutesAPIClient (Sandbox: {self.sandbox_name}): {log_action} task with routing key '{routing_key}'. Key in cache: {should}. Cache: {list(current_cached_keys)}.")
            return should
        else: # This is a baseline workload
            if routing_key is None:
                print(f"RoutesAPIClient (Baseline): Processing task, no routing key provided.")
                return True 
            
            should = routing_key not in current_cached_keys
            log_action = "Processing" if should else "Skipping"
            print(f"RoutesAPIClient (Baseline): {log_action} task with routing key '{routing_key}'. Key in cache: {not should}. Cache: {list(current_cached_keys)}.")
            return should

# Define Inbound Interceptors that will contain the actual execution logic
class _SelectiveWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    def __init__(self, next_interceptor: WorkflowInboundInterceptor, outer_interceptor: "SelectiveTaskInterceptor"):
        super().__init__(next_interceptor)
        self.outer_interceptor = outer_interceptor

    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        print(f"WORKFLOW INTERCEPTOR (INBOUND) STARTED for workflow type: {input.workflow_type}") # Your debug print
        routing_key = self.outer_interceptor._extract_routing_key(input.header.get('sd-routing-key'))
        if not await self.outer_interceptor._should_process_task_with_client("workflow", input.workflow_type, routing_key):
            print(f"WORKFLOW INTERCEPTOR (INBOUND): Skipping workflow {input.workflow_type} (key: {routing_key}) based on routing rules.")
            raise ApplicationError(
                f"Worker (sandbox: {self.outer_interceptor.sandbox_name or 'baseline'}) decided not to process workflow {input.workflow_type} with routing key '{routing_key}'",
                type="RoutingSkipDecision",
                non_retryable=True
            )
        return await self.next.execute_workflow(input)

class _SelectiveActivityInboundInterceptor(ActivityInboundInterceptor):
    def __init__(self, next_interceptor: ActivityInboundInterceptor, outer_interceptor: "SelectiveTaskInterceptor"):
        super().__init__(next_interceptor)
        self.outer_interceptor = outer_interceptor

    async def execute_activity(self, input: ExecuteActivityInput) -> Any:
        print(input)
        routing_key = self.outer_interceptor._extract_routing_key(input.header.get('sd-routing-key'))
        activity_name = str(input.fn.__name__)
        print(f"ACTIVITY INTERCEPTOR (INBOUND) STARTED for activity: {activity_name}") # Debug print

        if not await self.outer_interceptor._should_process_task_with_client("activity", activity_name, routing_key):
            print(f"ACTIVITY INTERCEPTOR (INBOUND): Skipping activity {activity_name} (key: {routing_key}) based on routing rules.")
            raise ApplicationError(
                f"Worker (sandbox: {self.outer_interceptor.sandbox_name or 'baseline'}) decided not to process activity {activity_name} with routing key '{routing_key}'",
                type="RoutingSkipDecision",
                non_retryable=True
            )
        return await self.next.execute_activity(input)


class SelectiveTaskInterceptor(Interceptor):
    """Interceptor that handles routing decisions for both workflow and activity tasks."""
    
    def __init__(self):
        super().__init__() 
        self.sandbox_name = os.getenv("SANDBOX_NAME", "")
        self.routes_client = RoutesAPIClient(sandbox_name=self.sandbox_name)
        print(f"SelectiveTaskInterceptor initialized. Sandbox: '{self.sandbox_name or 'baseline'}' using new RoutesAPIClient.")

    def _extract_routing_key(self, headers: Optional[dict]) -> Optional[str]:
        if not headers:
            return None
        
        routing_key_value = headers.get("sd-routing-key")
        if not routing_key_value:
            return None

        if isinstance(routing_key_value, bytes):
            return routing_key_value.decode()
        if isinstance(routing_key_value, str):
            return routing_key_value
        
        if isinstance(routing_key_value, (list, tuple)) and routing_key_value:
            val = routing_key_value[0]
            if isinstance(val, bytes):
                return val.decode()
            if isinstance(val, str):
                return val
        
        print(f"Warning: Unexpected type for routing key: {type(routing_key_value)}, value: {routing_key_value}")
        return None
    
    async def _should_process_task_with_client(self, task_type: str, task_name: str, routing_key: Optional[str]) -> bool:
        return await self.routes_client.should_process(routing_key)

    # This method is called by the Worker to set up workflow interception
    def intercept_workflow(self, next_inbound: WorkflowInboundInterceptor) -> WorkflowInboundInterceptor:
        print(f"SelectiveTaskInterceptor: intercept_workflow called for next: {type(next_inbound)}") # Debug print
        # Return an instance of your inbound interceptor, passing the next one in the chain and a reference to self
        return _SelectiveWorkflowInboundInterceptor(next_inbound, self)

    # This method is called by the Worker to set up activity interception
    def intercept_activity(self, next_inbound: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        print(f"SelectiveTaskInterceptor: intercept_activity called for next: {type(next_inbound)}") # Debug print
        # Return an instance of your inbound interceptor
        return _SelectiveActivityInboundInterceptor(next_inbound, self)


class SandboxAwareWorker:
    """
    Platform-provided worker wrapper that adds sandbox routing.
    """
    
    def __init__(self, task_queue: str, workflows: List[Any], activities: List[Any]):
        self.task_queue = task_queue
        self.workflows = workflows
        self.activities = activities
        self.sandbox_name = os.getenv("SANDBOX_NAME", "")
        
    async def run(self):
        """Run the sandbox-aware worker"""
        print(f"Starting SandboxAwareWorker...")
        print(f"Task Queue: {self.task_queue}")
        print(f"Sandbox Name: {self.sandbox_name or 'baseline'}")
        workflow_names = []
        for w in self.workflows:
            if hasattr(w, '__name__'):
                 workflow_names.append(w.__name__)
            elif hasattr(w, '__class__') and hasattr(w.__class__, '__name__'):
                 workflow_names.append(w.__class__.__name__)
            else:
                 workflow_names.append(str(w))
        print(f"Workflows: {workflow_names}")
        print(f"Activities: {len(self.activities)} activities registered")
        
        try:
            temporal_url = os.getenv("TEMPORAL_SERVER_URL", "temporal-server:7233")
            client = await Client.connect(temporal_url)
            print(f"Connected to Temporal server: {temporal_url}")
            
            interceptor = SelectiveTaskInterceptor() 
            
            worker = Worker(
                client,
                task_queue=self.task_queue,
                workflows=self.workflows,
                activities=self.activities,
                interceptors=[interceptor] 
            )
            
            print(f"Worker created successfully. Starting to poll for tasks...")
            await worker.run()
            
        except Exception as e:
            print(f"Error running worker: {e}")
            raise
