from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.models.expert import Expert, ExpertStatus
from app.db.models.payment import ExpertVerificationPayment, VerificationPaymentStatus
from app.db.models.user import CustomUser
from app.db.models.verification import VerificationDocument
from app.db.schemas.experts import (
    MyVerificationPaymentResponse,
    VerificationPaymentAttemptResponse,
    VerificationPaymentConfigResponse,
    VerificationPaymentRequest,
)
from app.db.session import get_db
from app.services.daraja import (
    DarajaConfigurationError,
    DarajaError,
    initiate_stk_push,
    is_daraja_configured,
    normalize_phone_number,
)


router = APIRouter(prefix="/api/experts", tags=["expert verification payments"])


def _payment_message(payment: ExpertVerificationPayment | None) -> str | None:
    if payment is None:
        return None
    if payment.status == VerificationPaymentStatus.PAID.value:
        return "Payment confirmed. Your application is now in review."
    if payment.status in {
        VerificationPaymentStatus.INITIATING.value,
        VerificationPaymentStatus.PENDING.value,
    }:
        return "Check your phone and approve the M-Pesa request to continue."
    return "Payment was not completed. You can try again."


def _latest_payment(db: Session, expert_id: int) -> ExpertVerificationPayment | None:
    return db.scalar(
        select(ExpertVerificationPayment)
        .where(ExpertVerificationPayment.expert_id == expert_id)
        .order_by(ExpertVerificationPayment.created_at.desc(), ExpertVerificationPayment.id.desc())
        .limit(1)
    )


@router.get("/payments/config/", response_model=VerificationPaymentConfigResponse)
def get_verification_payment_config() -> VerificationPaymentConfigResponse:
    return VerificationPaymentConfigResponse(
        available=is_daraja_configured(),
        amount=max(settings.expert_verification_fee_kes, 0),
    )


@router.get("/me/verification-payment/", response_model=MyVerificationPaymentResponse)
def get_my_verification_payment(
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MyVerificationPaymentResponse:
    expert = db.scalar(select(Expert).where(Expert.user_id == user.id))
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert application not found.")

    payment = _latest_payment(db, expert.id)
    documents_uploaded = db.scalar(
        select(func.count(VerificationDocument.id)).where(
            VerificationDocument.expert_id == expert.id
        )
    ) or 0
    return MyVerificationPaymentResponse(
        expert_id=expert.id,
        expert_status=ExpertStatus(expert.status),
        documents_uploaded=documents_uploaded,
        payment_id=payment.id if payment else None,
        payment_status=VerificationPaymentStatus(payment.status) if payment else None,
        amount=payment.amount if payment else None,
        customer_message=_payment_message(payment),
    )


@router.post(
    "/{expert_id}/payments/",
    response_model=VerificationPaymentAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_verification_payment(
    expert_id: int,
    payload: VerificationPaymentRequest,
    user: CustomUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VerificationPaymentAttemptResponse:
    expert = db.scalar(
        select(Expert)
        .where(Expert.id == expert_id, Expert.user_id == user.id)
        .with_for_update()
    )
    if expert is None:
        raise HTTPException(status_code=404, detail="Expert application not found.")
    if expert.status != ExpertStatus.AWAITING_PAYMENT.value:
        raise HTTPException(status_code=409, detail="This application is not awaiting payment.")

    documents_uploaded = db.scalar(
        select(func.count(VerificationDocument.id)).where(
            VerificationDocument.expert_id == expert.id
        )
    ) or 0
    if documents_uploaded == 0:
        raise HTTPException(status_code=400, detail="Upload at least one verification document before paying.")
    if not is_daraja_configured():
        raise HTTPException(status_code=503, detail="M-Pesa verification payments are not configured.")
    try:
        normalize_phone_number(payload.phone_number)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    previous = _latest_payment(db, expert.id)
    if previous and previous.status in {
        VerificationPaymentStatus.INITIATING.value,
        VerificationPaymentStatus.PENDING.value,
        VerificationPaymentStatus.PAID.value,
    }:
        return VerificationPaymentAttemptResponse(
            expert_id=expert.id,
            payment_id=previous.id,
            payment_status=VerificationPaymentStatus(previous.status),
            amount=previous.amount,
            customer_message=_payment_message(previous),
        )

    payment = ExpertVerificationPayment(
        expert_id=expert.id,
        amount=settings.expert_verification_fee_kes,
        currency="KES",
        status=VerificationPaymentStatus.INITIATING.value,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    try:
        provider_result = await initiate_stk_push(
            phone_number=payload.phone_number,
            amount=payment.amount,
            expert_id=expert.id,
        )
    except (DarajaConfigurationError, DarajaError, httpx.HTTPError) as error:
        payment.status = VerificationPaymentStatus.FAILED.value
        payment.result_code = -1
        payment.result_description = "M-Pesa request could not be started."
        db.commit()
        error_status = 503 if isinstance(error, DarajaConfigurationError) else 502
        raise HTTPException(
            status_code=error_status,
            detail="Could not start the M-Pesa request. Check the number and try again.",
        ) from error

    payment.status = VerificationPaymentStatus.PENDING.value
    payment.checkout_request_id = provider_result["checkout_request_id"]
    payment.merchant_request_id = provider_result["merchant_request_id"]
    db.commit()
    db.refresh(payment)
    return VerificationPaymentAttemptResponse(
        expert_id=expert.id,
        payment_id=payment.id,
        payment_status=VerificationPaymentStatus(payment.status),
        amount=payment.amount,
        customer_message=provider_result["customer_message"],
    )


@router.post("/payments/daraja/callback/", status_code=status.HTTP_200_OK)
async def daraja_callback(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    try:
        body = await request.json()
    except ValueError:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    if not isinstance(body, dict):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    callback_body = body.get("Body")
    if not isinstance(callback_body, dict):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    callback = callback_body.get("stkCallback")
    if not isinstance(callback, dict):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    checkout_request_id = callback.get("CheckoutRequestID")
    if not isinstance(checkout_request_id, str) or not checkout_request_id:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment = db.scalar(
        select(ExpertVerificationPayment)
        .where(ExpertVerificationPayment.checkout_request_id == checkout_request_id)
        .with_for_update()
    )
    if payment is None or payment.status == VerificationPaymentStatus.PAID.value:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    if payment.status == VerificationPaymentStatus.FAILED.value:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    try:
        raw_result_code = callback.get("ResultCode")
        if not isinstance(raw_result_code, (int, str)):
            return {"ResultCode": 0, "ResultDesc": "Accepted"}
        result_code = int(raw_result_code)
    except (TypeError, ValueError):
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    payment.result_code = result_code
    if result_code == 0:
        callback_metadata = callback.get("CallbackMetadata")
        items = callback_metadata.get("Item") if isinstance(callback_metadata, dict) else []
        items = items if isinstance(items, list) else []
        metadata = {
            item.get("Name"): item.get("Value")
            for item in items
            if isinstance(item, dict) and item.get("Name")
        }
        try:
            callback_amount = Decimal(str(metadata.get("Amount")))
        except (InvalidOperation, TypeError):
            callback_amount = Decimal("-1")
        receipt_number = metadata.get("MpesaReceiptNumber")
        duplicate_receipt = db.scalar(
            select(ExpertVerificationPayment.id).where(
                ExpertVerificationPayment.receipt_number == str(receipt_number),
                ExpertVerificationPayment.id != payment.id,
            )
        ) if receipt_number else None
        if callback_amount != Decimal(payment.amount) or not isinstance(receipt_number, str) or duplicate_receipt:
            payment.status = VerificationPaymentStatus.FAILED.value
            payment.result_description = "M-Pesa confirmation did not match the requested payment."
        else:
            payment.status = VerificationPaymentStatus.PAID.value
            payment.receipt_number = str(receipt_number)[:32]
            payment.result_description = "Payment confirmed."
            payment.paid_at = datetime.now(timezone.utc)
            expert = db.get(Expert, payment.expert_id)
            if expert and expert.status == ExpertStatus.AWAITING_PAYMENT.value:
                expert.status = ExpertStatus.PENDING.value
    else:
        payment.status = VerificationPaymentStatus.FAILED.value
        payment.result_description = "M-Pesa payment was not completed."

    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}