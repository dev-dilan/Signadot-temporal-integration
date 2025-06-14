import os
import asyncio
import time # For monotonic time
import aiohttp
from typing import List, Any, Optional, Set, Dict # Ensure Set is imported
from temporalio.api.common.v1 import Payload # Add this import
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
import temporalio.workflow as workflow # For accessing workflow context

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

class _SelectiveWorkflowInboundInterceptor(WorkflowInboundInterceptor):
    def __init__(self, next_interceptor: WorkflowInboundInterceptor, outer_interceptor: "SelectiveTaskInterceptor"):
        super().__init__(next_interceptor)
        self.outer_interceptor = outer_interceptor

    async def execute_workflow(self, input: ExecuteWorkflowInput) -> Any:
        print(f"WORKFLOW INTERCEPTOR (INBOUND) STARTED for workflow type: {input.workflow_type}")
        
        # In workflows, we can access headers through workflow.info().headers
        try:
            workflow_info = workflow.info()
            workflow_headers = workflow_info.headers if hasattr(workflow_info, 'headers') else {}
            print(f"DEBUG: Workflow headers from info: {workflow_headers}")
            
            # Try to get routing key from workflow context headers
            routing_key = None
            if 'sd-routing-key' in workflow_headers:
                routing_key = self.outer_interceptor._extract_routing_key(workflow_headers.get('sd-routing-key'))
            
            # Fallback to input headers if available
            if routing_key is None and hasattr(input, 'headers') and input.headers:
                print(f"DEBUG: Fallback to input headers: {input.headers}")
                routing_key = self.outer_interceptor._extract_routing_key(input.headers.get('sd-routing-key'))
            
            print(f"DEBUG: Final extracted routing key: {routing_key}")
            
        except Exception as e:
            print(f"DEBUG: Error accessing workflow context: {e}")
            # Fallback to input headers
            routing_key = self.outer_interceptor._extract_routing_key(
                input.headers.get('sd-routing-key') if hasattr(input, 'headers') and input.headers else None
            )
        
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
        print(f"ACTIVITY INTERCEPTOR (INBOUND) STARTED for activity: {input.fn.__name__}")
        
        # DEBUG: Print all available headers  
        print(f"DEBUG: Available headers: {input.headers}")
        print(f"DEBUG: Headers type: {type(input.headers)}")
        print(f"DEBUG: ExecuteActivityInput full: {input}")
        
        # Try multiple approaches to extract routing key
        routing_key = None
        
        # Method 1: Check input.headers
        if hasattr(input, 'headers') and input.headers:
            routing_key = self.outer_interceptor._extract_routing_key(input.headers.get('sd-routing-key'))
            print(f"DEBUG: Routing key from headers: {routing_key}")
        
        # Method 2: Check if there's a workflow context available
        if routing_key is None:
            try:
                # Try to access workflow context if this activity is running within a workflow
                workflow_info = workflow.info()
                if hasattr(workflow_info, 'headers') and workflow_info.headers:
                    routing_key = self.outer_interceptor._extract_routing_key(workflow_info.headers.get('sd-routing-key'))
                    print(f"DEBUG: Routing key from workflow context: {routing_key}")
            except Exception as e:
                print(f"DEBUG: No workflow context available for activity (this is normal for direct activity calls): {e}")
        
        # Method 3: Check input attributes for any header-like fields
        if routing_key is None:
            for attr_name in dir(input):
                if 'header' in attr_name.lower() or 'meta' in attr_name.lower():
                    try:
                        attr_value = getattr(input, attr_name)
                        print(f"DEBUG: Found attribute {attr_name}: {attr_value} (type: {type(attr_value)})")
                        if isinstance(attr_value, dict) and 'sd-routing-key' in attr_value:
                            routing_key = self.outer_interceptor._extract_routing_key(attr_value.get('sd-routing-key'))
                            print(f"DEBUG: Routing key from {attr_name}: {routing_key}")
                            break
                    except Exception as e:
                        print(f"DEBUG: Error accessing {attr_name}: {e}")
        
        print(f"DEBUG: Final extracted routing key: {routing_key}")
        
        activity_name = str(input.fn.__name__)

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

    def _extract_routing_key(self, header_payload: Optional[Any]) -> Optional[str]:
        """
        Extracts the string value from a header's Payload object or direct value.
        Enhanced with better debugging and error handling.
        """
        print(f"DEBUG: _extract_routing_key called with: {header_payload} (type: {type(header_payload)})")
        
        if not header_payload:
            print("DEBUG: No header_payload provided")
            return None
        
        # Handle Payload objects
        if isinstance(header_payload, Payload):
            if header_payload.data:
                try:
                    decoded = header_payload.data.decode('utf-8')
                    print(f"DEBUG: Successfully decoded routing key from Payload: '{decoded}'")
                    return decoded
                except UnicodeDecodeError:
                    print(f"Warning: Could not decode routing key from payload data as UTF-8: {header_payload.data}")
                    return None
            else:
                print(f"Warning: Routing key payload data is empty.")
                return None
        
        # Handle direct string values
        elif isinstance(header_payload, str):
            print(f"DEBUG: Header is string directly: '{header_payload}'")
            return header_payload
        
        # Handle bytes
        elif isinstance(header_payload, bytes):
            try:
                decoded = header_payload.decode('utf-8')
                print(f"DEBUG: Decoded bytes header: '{decoded}'")
                return decoded
            except UnicodeDecodeError:
                print(f"Warning: Could not decode raw bytes for routing key: {header_payload}")
                return None
        
        # Handle dict-like objects (in case headers are nested)
        elif hasattr(header_payload, '__getitem__') and hasattr(header_payload, 'keys'):
            print(f"DEBUG: Header payload is dict-like: {header_payload}")
            if 'data' in header_payload:
                return self._extract_routing_key(header_payload['data'])
            elif 'value' in header_payload:
                return self._extract_routing_key(header_payload['value'])
        
        else:
            print(f"Warning: Unexpected header payload type {type(header_payload)}. Value: {header_payload}")
            # Try to convert to string as last resort
            try:
                str_value = str(header_payload)
                if str_value and str_value != 'None':
                    print(f"DEBUG: Converted to string: '{str_value}'")
                    return str_value
            except Exception as e:
                print(f"Warning: Could not convert header payload to string: {e}")
            
            return None
    
    async def _should_process_task_with_client(self, task_type: str, task_name: str, routing_key: Optional[str]) -> bool:
        return await self.routes_client.should_process(routing_key)

    def intercept_workflow(self, next_inbound: WorkflowInboundInterceptor) -> WorkflowInboundInterceptor:
        print(f"SelectiveTaskInterceptor: intercept_workflow called for next: {type(next_inbound)}")
        return _SelectiveWorkflowInboundInterceptor(next_inbound, self)

    def intercept_activity(self, next_inbound: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        print(f"SelectiveTaskInterceptor: intercept_activity called for next: {type(next_inbound)}")
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

    

    # debug inteceptor registration in detail with debuging points 
    # async def run(self):
    #     """Run the sandbox-aware worker"""
    #     print(f"Starting SandboxAwareWorker...")
    #     print(f"Task Queue: {self.task_queue}")
    #     print(f"Sandbox Name: {self.sandbox_name or 'baseline'}")
    #     workflow_names = []
    #     for w in self.workflows:
    #         if hasattr(w, '__name__'):
    #             workflow_names.append(w.__name__)
    #         elif hasattr(w, '__class__') and hasattr(w.__class__, '__name__'):
    #             workflow_names.append(w.__class__.__name__)
    #         else:
    #             workflow_names.append(str(w))
    #     print(f"Workflows: {workflow_names}")
    #     print(f"Activities: {len(self.activities)} activities registered")
        
    #     try:
    #         temporal_url = os.getenv("TEMPORAL_SERVER_URL", "temporal-server:7233")
    #         client = await Client.connect(temporal_url)
    #         print(f"Connected to Temporal server: {temporal_url}")
            
    #         interceptor = SelectiveTaskInterceptor() 
            
    #         # ADD DEBUG: Explicitly check interceptor methods
    #         print(f"DEBUG: Interceptor has intercept_workflow: {hasattr(interceptor, 'intercept_workflow')}")
    #         print(f"DEBUG: Interceptor has intercept_activity: {hasattr(interceptor, 'intercept_activity')}")
    #         print(f"DEBUG: Interceptor type: {type(interceptor)}")
    #         print(f"DEBUG: Interceptor MRO: {type(interceptor).__mro__}")
            
    #         # Test interceptor methods directly
    #         try:
    #             from temporalio.worker._interceptor import WorkflowInboundInterceptor, ActivityInboundInterceptor
    #             mock_next_workflow_interceptor = create_autospec(WorkflowInboundInterceptor, instance=True)
    #             # Ensure the mock has an async execute_workflow if your interceptor might call it
    #             if hasattr(mock_next_workflow_interceptor, 'execute_workflow'):
    #                 mock_next_workflow_interceptor.execute_workflow = AsyncMock()

    #             mock_next_activity_interceptor = create_autospec(ActivityInboundInterceptor, instance=True)
    #             # Ensure the mock has an async execute_activity
    #             if hasattr(mock_next_activity_interceptor, 'execute_activity'):
    #                 mock_next_activity_interceptor.execute_activity = AsyncMock()
                
    #             workflow_result = interceptor.intercept_workflow(mock_next_workflow_interceptor)
    #             activity_result = interceptor.intercept_activity(mock_next_activity_interceptor)
                
    #             print(f"DEBUG: intercept_workflow returned: {type(workflow_result)}")
    #             print(f"DEBUG: intercept_activity returned: {type(activity_result)}")
    #         except Exception as e:
    #             print(f"DEBUG: Error testing interceptor methods: {e}")
            
    #         worker = Worker(
    #             client,
    #             task_queue=self.task_queue,
    #             workflows=self.workflows,
    #             activities=self.activities,
    #             interceptors=[interceptor]  # Make sure this is a list
    #         )
            
    #         print(f"Worker created successfully. Starting to poll for tasks...")
            
    #         # Try different ways to access worker internals
    #         worker_attrs = [attr for attr in dir(worker) if 'intercept' in attr.lower()]
    #         print(f"DEBUG: Worker attributes with 'intercept': {worker_attrs}")
            
    #         # Check if worker has any interceptor-related attributes
    #         for attr in ['_config', '_interceptors', '_workflow_interceptors', '_activity_interceptors']:
    #             if hasattr(worker, attr):
    #                 val = getattr(worker, attr)
    #                 if attr == '_config':
    #                     print(f"DEBUG: Worker._config.interceptors: {val.get('interceptors', 'Not found')}")
    #                 else:
    #                     print(f"DEBUG: Worker.{attr}: {val}")
            
    #         print(f"★★★ ABOUT TO START WORKER - interceptor methods should be called when first task arrives")
    #         await worker.run()
            
    #     except Exception as e:
    #         print(f"Error running worker: {e}")
    #         raise

