import base64

from app.services.payment_service import build_toss_basic_authorization, generate_toss_customer_key


def test_toss_basic_authorization_encodes_secret_with_trailing_colon():
    header = build_toss_basic_authorization("test_sk_example")

    assert header == f"Basic {base64.b64encode(b'test_sk_example:').decode('ascii')}"
    assert "test_sk_example" not in header


def test_toss_customer_key_matches_sdk_length_boundary():
    customer_key = generate_toss_customer_key()

    assert len(customer_key) <= 50
    assert "_" in customer_key
    assert customer_key.startswith("cust_")
