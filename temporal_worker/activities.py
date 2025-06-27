import uuid
import asyncio
from decimal import Decimal
from temporalio import activity
from models import WithdrawRequest, WithdrawResponse, DepositRequest, DepositResponse

class BankingActivities:
    """Banking activities implementation"""
    
    @activity.defn
    async def withdraw(self, request: WithdrawRequest) -> WithdrawResponse:
        """Withdraw money from account"""
        activity.logger.info(f"Processing withdrawal: {request.account_id}, amount: {request.amount}")
        
        try:
            # Simulate account balance check
            current_balance = await self._get_account_balance(request.account_id)
            
            if current_balance < Decimal(request.amount):
                return WithdrawResponse(
                    transaction_id="",
                    account_id=request.account_id,
                    amount=request.amount,
                    balance_after=str(current_balance),
                    success=False,
                    message="Insufficient funds"
                )
            
            # Simulate withdrawal processing time
            await asyncio.sleep(0.5)
            
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Calculate new balance
            new_balance = current_balance - Decimal(request.amount)
            
            # Simulate updating account balance
            await self._update_account_balance(request.account_id, new_balance)
            
            activity.logger.info(f"Withdrawal successful: {transaction_id}")
            
            return WithdrawResponse(
                transaction_id=transaction_id,
                account_id=request.account_id,
                amount=request.amount,
                balance_after=str(new_balance),
                success=True,
                message="Withdrawal successful"
            )
            
        except Exception as e:
            activity.logger.error(f"Withdrawal failed: {str(e)}")
            return WithdrawResponse(
                transaction_id="",
                account_id=request.account_id,
                amount=request.amount,
                balance_after='0',
                success=False,
                message=f"Withdrawal failed: {str(e)}"
            )
    
    @activity.defn
    async def deposit(self, request: DepositRequest) -> DepositResponse:
        """Deposit money to account"""
        activity.logger.info(f"Processing deposit: {request.account_id}, amount: {request.amount}")
        
        try:
            # Get current balance
            current_balance = await self._get_account_balance(request.account_id)
            
            # Simulate deposit processing time
            await asyncio.sleep(0.3)
            
            # Generate transaction ID
            transaction_id = str(uuid.uuid4())
            
            # Calculate new balance
            new_balance = current_balance + Decimal(request.amount)
            
            # Simulate updating account balance
            await self._update_account_balance(request.account_id, new_balance)
            
            activity.logger.info(f"Deposit successful: {transaction_id}")
            
            return DepositResponse(
                transaction_id=transaction_id,
                account_id=request.account_id,
                amount=request.amount,
                balance_after=str(new_balance),
                success=True,
                message="Deposit successful"
            )
            
        except Exception as e:
            activity.logger.error(f"Deposit failed: {str(e)}")
            return DepositResponse(
                transaction_id="",
                account_id=request.account_id,
                amount=request.amount,
                balance_after='0',
                success=False,
                message=f"Deposit failed: {str(e)}"
            )
    
    async def _get_account_balance(self, account_id: str) -> Decimal:
        """Simulate getting account balance from database"""
        # In real implementation, this would query actual database
        # For demo purposes, return mock balances
        mock_balances = {
            "acc_001": Decimal('1000.00'),
            "acc_002": Decimal('500.00'),
            "acc_003": Decimal('2500.00'),
            "acc_004": Decimal('750.00')
        }
        
        # Simulate database query delay
        await asyncio.sleep(0.1)
        
        return mock_balances.get(account_id, Decimal('1000.00'))
    
    async def _update_account_balance(self, account_id: str, new_balance: Decimal):
        """Simulate updating account balance in database"""
        # In real implementation, this would update actual database
        activity.logger.info(f"Updated balance for {account_id}: {new_balance}")
        
        # Simulate database update delay
        await asyncio.sleep(0.1)