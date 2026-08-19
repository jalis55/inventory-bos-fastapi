import uuid

def generate_uuid() -> str:
    """
    Generate a random UUID (UUID4) as a string.
    """
    return str(uuid.uuid4())


