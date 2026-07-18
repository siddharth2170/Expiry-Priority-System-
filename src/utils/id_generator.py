import uuid


def generate_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def generate_food_id() -> str:
    return generate_id("FOOD")


def generate_request_id() -> str:
    return generate_id("REQ")
