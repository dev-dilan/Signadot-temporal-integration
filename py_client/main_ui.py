import os
import asyncio
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from decimal import Decimal, InvalidOperation
from baggage import Baggage

# Assuming client.py and models.py are in the same directory or accessible
# Ensure this import path is correct based on your project structure
from client import start_workflow_with_routing
from models import PaymentDetails

app = FastAPI()

# Create a 'templates' directory in the same location as main_ui.py
# and place your index.html file there.
templates = Jinja2Templates(directory="templates")

# Mock account data for dropdowns - in a real app, this might come from a database
MOCK_ACCOUNTS = ["acc_001", "acc_002", "acc_003", "acc_004", "acc_005_large_balance"]

@app.get("/", response_class=HTMLResponse)
async def get_workflow_form(request: Request):
    """Serves the HTML form."""
    return templates.TemplateResponse("index.html", {"request": request, "accounts": MOCK_ACCOUNTS})

@app.post("/api/start-workflow")
async def handle_start_workflow(
    request: Request,
    from_account: str = Form(...),
    to_account: str = Form(...),
    amount: str = Form(...),
    reference: str = Form(""), # Optional, defaults to empty string
):
    """API endpoint to receive form data and start the Temporal workflow."""
    
    try:
        baggage = Baggage()
        
        # Basic validation
        if from_account == to_account:
            return JSONResponse(status_code=400, content={"error": "From and To accounts cannot be the same."})
        
        try:
            parsed_amount = Decimal(amount)
            if parsed_amount <= 0:
                return JSONResponse(status_code=400, content={"error": "Amount must be a positive number."})
        except InvalidOperation:
            return JSONResponse(status_code=400, content={"error": "Invalid amount format."})

        payment = PaymentDetails(
            from_account=from_account,
            to_account=to_account,
            amount=str(parsed_amount), # PaymentDetails expects string, validates internally
            reference=reference
        )
        
        # Use None if routing_key is empty string, otherwise pass the value
        effective_routing_key = baggage.extract_routing_key_from_baggage(request.headers['baggage']) if request.headers.get('baggage') else None        

        result = await start_workflow_with_routing(
            payment_details=payment,
            routing_key=effective_routing_key
        )
        return JSONResponse(content=result)
        
    except ValueError as ve: # Catch validation errors from PaymentDetails
        return JSONResponse(status_code=400, content={"error": str(ve)})
    except Exception as e:
        # Log the full error for debugging on the server
        print(f"Error starting workflow: {e}")
        return JSONResponse(status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"})

# To run this application:
# 1. Make sure FastAPI and Uvicorn are installed: pip install fastapi uvicorn python-multipart jinja2
# 2. Create a directory named "templates" in the same directory as main_ui.py.
# 3. Put the index.html file (provided next) into the "templates" directory.
# 4. Run from your terminal: uvicorn main_ui:app --reload
# 5. Open your browser to http://127.0.0.1:8000
