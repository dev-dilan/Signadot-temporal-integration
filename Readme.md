# Signadot Temporal integration with Kubernetes

This repository demonstrates an example of integrating Signadot with Temporal workflows.

## Prerequisites

*   A running Kubernetes cluster.
*   `kubectl` installed and configured to communicate with your cluster.

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
3.  **Create a namespace for Temporal:**
    ```bash
    kubectl create ns temporal
    ```
4.  **Deploy the temporal server to Kubernetes:**
    ```bash
    kubectl apply -f k8s/temporal/ -n temporal
    ```
4.  **Deploy the application to Kubernetes:**
    ```bash
    kubectl apply -f k8s/ -n temporal
6.  **Access the services:**
    To access the services, you'll need to forward their ports from the cluster to your local machine. Open a separate terminal for each port-forward command.

    *   **Temporal Admin Dashboard:**
        ```bash
        kubectl port-forward svc/temporal-web 8080:8080 -n temporal
        ```
        The dashboard will be available at http://localhost:8080.

    *   **Workflow Web GUI:**
        ```bash
        kubectl port-forward svc/web-gui 8000:8000 -n temporal
        ```
        The GUI will be available at http://localhost:8000.

## Observing Workflow Execution

1.  Ensure you have port-forwarded the services as described in the "Getting Started" section.
2.  Open the **Workflow Web GUI** at http://localhost:8000.
3.  Fill out the "Money Transfer Form" and click "Submit".
4.  Navigate to the **Temporal Admin Dashboard** at http://localhost:8080.
5.  Go to the "Workflows" section. You should see the newly created workflow.
6.  Clicking on the workflow will show you its details, including the input payload, headers, execution history, and current status, often presented in JSON format.

## Cleaning Up Resources

To remove all the Kubernetes resources and the namespace created for this example, run:
```bash
kubectl delete ns temporal
```