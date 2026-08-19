import uuid
from app.utils.helpers import generate_uuid

def test_generate_uuid_returns_valid_uuid_string():
    val = generate_uuid()
    assert isinstance(val, str)
    # Verify it is a valid UUID
    parsed = uuid.UUID(val)
    assert str(parsed) == val
