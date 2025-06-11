# Signadot Temporal integration

This repository demonstrates an example of integrating Signadot with Temporal workflows.

## Getting Started

To get started with this example, follow these steps:

1.  **Clone the repository:**
    ```bash
    git clone <YOUR_REPOSITORY_URL>
    ```
2.  **Navigate to the repository directory:**
    ```bash
    cd <REPOSITORY_DIRECTORY_NAME>
    ```
3.  **Make the scripts executable:**
    ```bash
    chmod +x init.sh
    chmod +x down.sh
    ```
4.  **Run the initialization script:**
    ```bash
    ./init.sh
    ```

After running `init.sh`, the following services will be available:

*   **Temporal Admin Dashboard:** http://localhost:8080 - Provides an interface for managing and monitoring your Temporal workflows.
*   **Workflow Web GUI:** http://localhost:8000 - A web interface for interacting with and managing workflow tasks.

## Observing Workflow Execution

1.  Open the **Workflow Web GUI** at http://localhost:8000.
2.  Fill out the "Money Transfer Form" and click "Submit".
3.  Navigate to the **Temporal Admin Dashboard** at http://localhost:8080.
4.  Go to the "Workflows" section. You should see the newly created workflow.
5.  Clicking on the workflow will show you its details, including the input payload, headers, execution history, and current status, often presented in JSON format.

## Injecting Headers into Workflows

Navigate to the `node_client/client_server.js` file to see this in context. When preparing the `workflowOptions` for starting a workflow, you can include a `headers` object:

```javascript        
        const workflowOptions = {
            args: [paymentDetails], // Workflow arguments are passed as an array
            taskQueue: TASK_QUEUE,
            workflowId: workflowId,
            headers: {
                // Example: setting a 'sd-routing-key'
                'sd-routing-key': defaultPayloadConverter.toPayload('abc-123'),
            },
        };
```

## Cleaning Up Resources

To stop all running services, remove the containers, networks, and volumes created by `docker-compose up`, execute the cleanup script:

```bash
./down.sh
```