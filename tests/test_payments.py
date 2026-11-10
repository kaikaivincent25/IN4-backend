from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.dependencies import get_current_user
from app.db.models import CustomUser, Expert, ExpertStatus, ExpertVerificationPayment, VerificationDocument
from app.db.models.payment import VerificationPaymentStatus
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture()
def payment_client() -> Iterator[tuple[TestClient, sessionmaker[Session], int]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with test_session() as db:
        user = CustomUser(
            email="applicant@example.com",
            password="unused-test-hash",
            first_name="Sam",
            last_name="Applicant",
        )
        db.add(user)
        db.commit()
        user_id = user.id

    authenticated_user = CustomUser(
        id=user_id,
        email="applicant@example.com",
        password="unused-test-hash",
        first_name="Sam",
        last_name="Applicant",
    )

    def override_get_db() -> Iterator[Session]:
        with test_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    try:
        with TestClient(app) as client:
            yield client, test_session, user_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_application(
    test_session: sessionmaker[Session],
    user_id: int,
    slug: str,
) -> int:
    with test_session() as db:
        expert = Expert(
            user_id=user_id,
            profession="doctor",
            license_number="KE-MD-12345",
            license_issuer="Kenya Medical Board",
            status=ExpertStatus.AWAITING_PAYMENT.value,
            slug=slug,
        )
        db.add(expert)
        db.flush()
        db.add(
            VerificationDocument(
                expert_id=expert.id,
                original_name="license.pdf",
                content_type="application/pdf",
                storage_key=f"{slug}-document-key",
            )
        )
        db.commit()
        return expert.id


def _enable_test_payments(monkeypatch: pytest.MonkeyPatch, mock_stk_push) -> None:
    monkeypatch.setattr("app.api.payments.is_daraja_configured", lambda: True)
    monkeypatch.setattr("app.api.payments.settings.expert_verification_fee_kes", 150)
    monkeypatch.setattr("app.api.payments.initiate_stk_push", mock_stk_push)


def test_new_expert_application_waits_for_payment(payment_client) -> None:
    client, _, _ = payment_client

    response = client.post(
        "/api/experts/apply/",
        json={
            "profession": "doctor",
            "license_number": "KE-MD-12345",
            "license_issuer": "Kenya Medical Board",
        },
    )

    assert response.status_code == 201
    assert response.json()["application_status"] == "awaiting_payment"
    assert response.json()["expert_id"]


@pytest.mark.anyio
async def test_payment_request_is_idempotent_and_callback_moves_application_to_review(
    payment_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session, user_id = payment_client
    expert_id = _create_application(test_session, user_id, "payment-success")
    call_count = 0

    async def fake_stk_push(phone_number: str, amount: int, expert_id: int) -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        assert phone_number == "0712345678"
        assert amount == 150
        return {
            "checkout_request_id": "ws_CO_success",
            "merchant_request_id": "merchant_success",
            "customer_message": "Approve on your phone.",
        }

    _enable_test_payments(monkeypatch, fake_stk_push)
    endpoint = f"/api/experts/{expert_id}/payments/"
    payload = {"phone_number": "0712345678"}

    first = client.post(endpoint, json=payload)
    second = client.post(endpoint, json=payload)

    assert first.status_code == 201
    assert first.json()["payment_status"] == VerificationPaymentStatus.PENDING.value
    assert second.json()["payment_id"] == first.json()["payment_id"]
    assert call_count == 1

    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_success",
                "ResultCode": 0,
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 150},
                        {"Name": "MpesaReceiptNumber", "Value": "QW12345678"},
                    ]
                },
            }
        }
    }
    assert client.post("/api/experts/payments/daraja/callback/", json=callback).status_code == 200
    assert client.post("/api/experts/payments/daraja/callback/", json=callback).status_code == 200

    with test_session() as db:
        expert = db.get(Expert, expert_id)
        payment = db.scalar(
            select(ExpertVerificationPayment).where(
                ExpertVerificationPayment.expert_id == expert_id
            )
        )
        assert expert.status == ExpertStatus.PENDING.value
        assert payment.status == VerificationPaymentStatus.PAID.value
        assert payment.receipt_number == "QW12345678"


@pytest.mark.anyio
async def test_callback_amount_mismatch_fails_payment_and_does_not_queue_application(
    payment_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, test_session, user_id = payment_client
    expert_id = _create_application(test_session, user_id, "payment-mismatch")

    async def fake_stk_push(phone_number: str, amount: int, expert_id: int) -> dict[str, str]:
        return {
            "checkout_request_id": "ws_CO_mismatch",
            "merchant_request_id": "merchant_mismatch",
            "customer_message": "Approve on your phone.",
        }

    _enable_test_payments(monkeypatch, fake_stk_push)
    assert client.post(
        f"/api/experts/{expert_id}/payments/",
        json={"phone_number": "254712345678"},
    ).status_code == 201

    callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_mismatch",
                "ResultCode": 0,
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": 149},
                        {"Name": "MpesaReceiptNumber", "Value": "QW87654321"},
                    ]
                },
            }
        }
    }
    client.post("/api/experts/payments/daraja/callback/", json=callback)

    with test_session() as db:
        expert = db.get(Expert, expert_id)
        payment = db.scalar(
            select(ExpertVerificationPayment).where(
                ExpertVerificationPayment.expert_id == expert_id
            )
        )
        assert expert.status == ExpertStatus.AWAITING_PAYMENT.value
        assert payment.status == VerificationPaymentStatus.FAILED.value


@pytest.mark.anyio
async def test_failed_attempt_can_be_retried(payment_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, test_session, user_id = payment_client
    expert_id = _create_application(test_session, user_id, "payment-retry")
    attempts = 0

    async def fake_stk_push(phone_number: str, amount: int, expert_id: int) -> dict[str, str]:
        nonlocal attempts
        attempts += 1
        return {
            "checkout_request_id": f"ws_CO_retry_{attempts}",
            "merchant_request_id": f"merchant_retry_{attempts}",
            "customer_message": "Approve on your phone.",
        }

    _enable_test_payments(monkeypatch, fake_stk_push)
    endpoint = f"/api/experts/{expert_id}/payments/"
    first = client.post(endpoint, json={"phone_number": "0712345678"})
    failed_callback = {
        "Body": {
            "stkCallback": {
                "CheckoutRequestID": "ws_CO_retry_1",
                "ResultCode": 1032,
                "ResultDesc": "Request cancelled by user.",
            }
        }
    }
    client.post("/api/experts/payments/daraja/callback/", json=failed_callback)
    second = client.post(endpoint, json={"phone_number": "0712345678"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["payment_id"] != first.json()["payment_id"]
    assert attempts == 2


def test_documents_can_be_uploaded_while_application_awaits_payment(
    payment_client,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    client, test_session, user_id = payment_client
    expert_id = _create_application(test_session, user_id, "payment-documents")
    monkeypatch.setattr("app.api.experts._PRIVATE_DOCUMENTS", tmp_path)

    response = client.post(
        f"/api/experts/{expert_id}/documents/",
        files={"file": ("license.pdf", b"%PDF-1.7\nverification", "application/pdf")},
    )

    assert response.status_code == 201
    assert client.get("/api/experts/me/verification-payment/").json()["documents_uploaded"] == 2
