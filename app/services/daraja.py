import base64
import re
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from pydantic import SecretStr

from app.core.config import settings


class DarajaError(Exception):
    pass


class DarajaConfigurationError(DarajaError):
    pass


def is_daraja_configured() -> bool:
    callback = urlparse(settings.daraja_callback_url or "")
    return all(
        (
            settings.expert_verification_fee_kes > 0,
            settings.daraja_environment in {"sandbox", "production"},
            settings.daraja_consumer_key,
            settings.daraja_consumer_secret,
            settings.daraja_shortcode,
            settings.daraja_passkey,
            callback.scheme == "https",
            bool(callback.netloc),
        )
    )


def normalize_phone_number(value: str) -> str:
    phone = re.sub(r"[\s()+-]", "", value)
    if phone.startswith("0"):
        phone = f"254{phone[1:]}"
    elif re.fullmatch(r"[17]\d{8}", phone):
        phone = f"254{phone}"
    if not re.fullmatch(r"254[17]\d{8}", phone):
        raise ValueError("Enter a valid Kenyan M-Pesa number, such as 0712345678.")
    return phone


def _secret_value(secret: SecretStr | None) -> str:
    if secret is None:
        raise DarajaConfigurationError("Daraja credentials are not configured.")
    return secret.get_secret_value()


def _api_base_url() -> str:
    if settings.daraja_environment not in {"sandbox", "production"}:
        raise DarajaConfigurationError("DARAJA_ENVIRONMENT must be sandbox or production.")
    if settings.daraja_environment == "production":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"


async def initiate_stk_push(phone_number: str, amount: int, expert_id: int) -> dict[str, str]:
    if not is_daraja_configured():
        raise DarajaConfigurationError("M-Pesa verification payments are not configured.")

    phone = normalize_phone_number(phone_number)
    base_url = _api_base_url()
    consumer_key = _secret_value(settings.daraja_consumer_key)
    consumer_secret = _secret_value(settings.daraja_consumer_secret)
    shortcode = settings.daraja_shortcode
    passkey = _secret_value(settings.daraja_passkey)
    timestamp = datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{shortcode}{passkey}{timestamp}".encode("utf-8")
    ).decode("ascii")

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.get(
            f"{base_url}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(consumer_key, consumer_secret),
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise DarajaError("Daraja did not return an access token.")

        response = await client.post(
            f"{base_url}/mpesa/stkpush/v1/processrequest",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "BusinessShortCode": shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone,
                "PartyB": shortcode,
                "PhoneNumber": phone,
                "CallBackURL": settings.daraja_callback_url,
                "AccountReference": f"IN4{expert_id}"[:12],
                "TransactionDesc": "IN4 verify",
            },
        )
        response.raise_for_status()
        result = response.json()

    if result.get("ResponseCode") != "0":
        raise DarajaError(str(result.get("errorMessage") or "Daraja rejected the payment request."))
    checkout_request_id = result.get("CheckoutRequestID")
    merchant_request_id = result.get("MerchantRequestID")
    if not checkout_request_id or not merchant_request_id:
        raise DarajaError("Daraja did not return payment request identifiers.")
    return {
        "checkout_request_id": str(checkout_request_id),
        "merchant_request_id": str(merchant_request_id),
        "customer_message": str(result.get("CustomerMessage") or "Check your phone to complete payment."),
    }