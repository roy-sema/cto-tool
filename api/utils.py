import hashlib
import hmac

from django.utils.dateparse import parse_datetime


# taken from https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries#python-example
def verify_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256.

    Args:
        payload_body: original request body to verify
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)
    """
    if not signature_header:
        return False
    msg = payload_body.encode("utf-8")
    secret_token = secret_token.encode("utf-8")

    hash_object = hmac.new(key=secret_token, msg=msg, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


def parse_date_param(request, param_name, payload=False):
    date_str = request.query_params.get(param_name) if not payload else request.data.get(param_name)

    return parse_datetime(date_str) if date_str else None
