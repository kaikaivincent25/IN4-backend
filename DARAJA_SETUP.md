# Daraja Verification Payments

Expert applications are saved as `awaiting_payment`. The staff review queue receives an application only after Daraja confirms a successful STK Push with the configured amount and an M-Pesa receipt number.

Configure these backend environment variables:

```text
DARAJA_ENVIRONMENT=sandbox
DARAJA_CONSUMER_KEY=<Safaricom Daraja consumer key>
DARAJA_CONSUMER_SECRET=<Safaricom Daraja consumer secret>
DARAJA_SHORTCODE=<Paybill shortcode>
DARAJA_PASSKEY=<STK Push passkey>
DARAJA_CALLBACK_URL=https://<public-backend-host>/api/experts/payments/daraja/callback/
EXPERT_VERIFICATION_FEE_KES=<approved whole-KES fee>
```

The callback must be reachable over HTTPS. Use Safaricom sandbox credentials and a public HTTPS callback tunnel for testing. Set `DARAJA_ENVIRONMENT=production` only after a successful sandbox test and production credential approval. The API reports payments unavailable while any required setting is missing or the fee is zero.

Payment attempts and provider identifiers are stored without retaining raw callback payloads or the applicant's phone number. Duplicate requests reuse an active attempt; failed attempts can be retried. A failed or rejected verification does not trigger an automatic refund. Define the refund policy and support procedure before enabling a non-zero fee in production.