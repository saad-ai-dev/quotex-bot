"""ID generation utilities for the Quotex Alert Intelligence system.

ALERT-ONLY system -- IDs are used for signal tracking, not trade orders.
"""

import uuid


def generate_signal_id() -> str:
    """Generate a unique signal ID using UUID4."""
    return str(uuid.uuid4())
