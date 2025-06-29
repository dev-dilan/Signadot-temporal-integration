from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from models import PaymentDetails, WithdrawRequest, DepositRequest
from activities import BankingActivities

@workflow.defn
class MoneyTransferWorkflow:
    """Baseline money transfer workflow - 2 step process"""
    
    @workflow.run
    async def run(self, payment_details: PaymentDetails) -> str:
        """Execute money transfer workflow"""
        
        workflow.logger.info(f"Starting money transfer: {payment_details.from_account} -> {payment_details.to_account}, amount: {payment_details.amount}")
        
        try:
            
            # Step 1: Withdraw money from source account
            withdraw_request = WithdrawRequest(
                account_id=payment_details.from_account,
                amount=payment_details.amount,
                reference=payment_details.reference
            )
            
            withdraw_result = await workflow.execute_activity(
                BankingActivities.withdraw,
                withdraw_request,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=10)
                )
            )
            
            if not withdraw_result.success:
                workflow.logger.error(f"Withdrawal failed: {withdraw_result.message}")
                return f"Transfer failed: {withdraw_result.message}"
            
            workflow.logger.info(f"Withdrawal successful: {withdraw_result.transaction_id}")
            
            # Step 2: Deposit money to destination account
            deposit_request = DepositRequest(
                account_id=payment_details.to_account,
                amount=payment_details.amount,
                reference=payment_details.reference
            )
            
            deposit_result = await workflow.execute_activity(
                BankingActivities.deposit,
                deposit_request,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=10)
                )
            )
            
            if not deposit_result.success:
                workflow.logger.error(f"Deposit failed: {deposit_result.message}")
                # In production, you might want to implement compensation logic here
                # to reverse the withdrawal
                return f"Transfer partially failed: Withdrawal succeeded but deposit failed - {deposit_result.message}"
            
            workflow.logger.info(f"Deposit successful: {deposit_result.transaction_id}")
            workflow.logger.info(f"Money transfer completed successfully")
            
            return f"Transfer complete: {withdraw_result.transaction_id} -> {deposit_result.transaction_id}"
            
        except Exception as e:
            workflow.logger.error(f"Workflow failed with exception: {str(e)}")
            return f"Transfer failed: {str(e)}"