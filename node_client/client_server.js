// client_server.js
import express from 'express';
import bodyParser from 'body-parser';
import path from 'path';
import { fileURLToPath } from 'url';
import { Connection, Client, defaultPayloadConverter } from '@temporalio/client';
import { v4 as uuidv4 } from 'uuid';

// --- Configuration ---
const TEMPORAL_SERVER_URL = process.env.TEMPORAL_SERVER_URL || 'localhost:7233';
const TASK_QUEUE = process.env.TASK_QUEUE || 'money-transfer';
const PORT = process.env.PORT || 3000;

// --- Helper for __dirname in ES modules ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Temporal Client Logic ---
/**
 * @typedef {object} PaymentDetails
 * @property {string} from_account
 * @property {string} to_account
 * @property {string} amount - String representation of a number
 * @property {string} [reference]
 * @property {string} [currency] - Defaults to "USD"
 */

async function startWorkflowWithRouting(paymentDetails, routingKey = null) {
    let connection;
    try {
        connection = await Connection.connect({ address: TEMPORAL_SERVER_URL });
        const client = new Client({
            connection,
        });

        const workflowId = `money-transfer-${uuidv4()}`;
        const workflowOptions = {
            args: [paymentDetails], // Workflow arguments are passed as an array
            taskQueue: TASK_QUEUE,
            workflowId: workflowId,
            headers: {
                'sd-routing-key': defaultPayloadConverter.toPayload('abc-123')
            },
        };

        // Inside your startWorkflowWithRouting function
        // if (routingKey && routingKey.trim() !== "") {
        //     const headerKey = 'sd-routing-key';
        //     const headerValue = routingKey;
        //     const payload = defaultPayloadConverter.toPayload(headerValue);

        //     console.log(`Attempting to set header: '${headerKey}' with value: '${headerValue}'`);
        //     console.log('Created Payload object:', payload);
        //     // You can inspect payload.metadata and payload.data
        //     // For example, to see the encoding string from metadata:
        //     if (payload.metadata && payload.metadata.encoding) {
        //         try {
        //             // The 'encoding' field in metadata is a Uint8Array representing the encoding type string
        //             const encodingType = Buffer.from(payload.metadata.encoding).toString('utf-8');
        //             console.log('Payload metadata encoding type:', encodingType); // e.g., "json/plain"
        //         } catch (e) {
        //             console.error('Error decoding payload.metadata.encoding:', e);
        //         }
        //     }
        //     if (payload.data) {
        //         console.log('Payload data (as string, if applicable):', Buffer.from(payload.data).toString('utf-8'));
        //     }

        //     workflowOptions.headers[headerKey] = payload;
        // }
        // Log the whole options object again
        // console.log("Final workflow options before start:", JSON.stringify(workflowOptions, null, 2));
        // Note: JSON.stringify won't fully represent Uint8Array content in a human-readable way for 'data'
        // but it will show the structure.
        
        const handle = await client.workflow.start('MoneyTransferWorkflow', workflowOptions);

        const resultMessage = `Started workflow with ID: ${handle.workflowId}, Run ID: ${handle.firstExecutionRunId}, Routing Key: ${routingKey || 'None (baseline)'}`;
        console.log(resultMessage);
        return {
            message: resultMessage,
            workflow_id: handle.workflowId,
            run_id: handle.firstExecutionRunId,
            routing_key_used: routingKey || 'baseline',
        };
    } catch (error) {
        console.error(`Failed to start workflow. Is Temporal server running at ${TEMPORAL_SERVER_URL} and worker for task queue '${TASK_QUEUE}' available?`, error);
        // Re-throw a more specific error or handle as needed
        throw new Error(`Failed to start workflow: ${error.message}`);
    } finally {
        // Connection closing is usually handled automatically by the SDK upon client disposal
        // or when the process exits. For short-lived operations, explicit close isn't always critical.
        // if (connection) {
        //     await connection.close();
        // }
    }
}

// --- Express Application Setup ---
const app = express();

// Middleware
app.use(bodyParser.urlencoded({ extended: true })); // For parsing application/x-www-form-urlencoded

// Serve static files (HTML, CSS, JS for the frontend)
// Create a 'templates' directory at the same level as client_server.js
app.use(express.static(path.join(__dirname, 'templates')));

// --- Routes ---
// Serve the HTML form
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

// API endpoint to start the workflow
app.post('/api/start-workflow', async (req, res) => {
    const { from_account, to_account, amount, reference, routing_key } = req.body;

    try {
        // Basic validation (mirroring Python FastAPI app)
        if (!from_account || !to_account || !amount) {
            return res.status(400).json({ error: "Missing required fields: from_account, to_account, amount." });
        }
        if (from_account === to_account) {
            return res.status(400).json({ error: "From and To accounts cannot be the same." });
        }
        
        const parsedAmount = parseFloat(amount);
        if (isNaN(parsedAmount) || parsedAmount <= 0) {
            return res.status(400).json({ error: "Amount must be a positive number." });
        }

        // Ensure your Temporal workflow expects PaymentDetails as the first argument
        const paymentDetails = {
            from_account,
            to_account,
            amount: String(parsedAmount), // Workflow expects string amount
            reference: reference || "",
            currency: "USD" // Matches Python model default
        };

        const effectiveRoutingKey = (routing_key && routing_key.trim() !== "") ? routing_key.trim() : null;

        const result = await startWorkflowWithRouting(paymentDetails, effectiveRoutingKey);
        res.json(result);

    } catch (error) {
        console.error('Error in /api/start-workflow:', error);
        if (error.message && error.message.includes('Failed to connect') || error.message.includes('UNAVAILABLE')) {
             return res.status(503).json({ error: `Service Unavailable: Could not connect to Temporal server at ${TEMPORAL_SERVER_URL} or worker not available.` });
        }
        res.status(500).json({ error: `An unexpected error occurred: ${error.message}` });
    }
});

// --- Start Server ---
app.listen(PORT, () => {
    console.log(`Node.js client UI server running on http://localhost:${PORT}`);
    console.log(`Attempting to connect to Temporal server at: ${TEMPORAL_SERVER_URL}`);
    console.log(`Using task queue: ${TASK_QUEUE}`);
});

// For graceful shutdown
process.on('SIGINT', () => {
    console.log('SIGINT signal received: closing HTTP server');
    // Add any cleanup logic here if necessary
    process.exit(0);
});
