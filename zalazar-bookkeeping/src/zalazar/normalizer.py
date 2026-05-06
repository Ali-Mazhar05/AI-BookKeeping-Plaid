import re
from typing import Optional
from decimal import Decimal

# Patterns applied in order (Milestone 3.1)
PROCESSOR_PREFIXES = [
    r"^SQ \*", r"^SQ\b", r"^APP\b", r"^CA\*", r"^GOOGLE \*", r"^APPLE\.COM/BILL"
]
MARKETPLACE_PREFIXES = [
    r"^PAYPAL \*", r"^AMZN MKTP\b", r"^PP\*", r"^PYPL\b", r"^VENMO\b", r"^ZELLE\b",
    r"^AMZN Mktp\b", r"^AMAZON\.COM\b", r"^CASH\b", r"^TST\*", r"^TRP\*", r"^DD \*",
    r"^UBR\*", r"^LYFT\*"
]
REFERENCE_TAILS = [
    r"\*[A-Z0-9]{4,}$", r"\d{10,}$"
]
LOCATION_TOKENS = [
    r",\s*[A-Z]{2}$", # State abbreviations
]

def clean_vendor(raw: str) -> str:
    """Pure function. Input: raw Plaid description. Output: cleaned merchant."""
    if not raw:
        return ""
        
    cleaned = raw
    
    # 1. Payment processor prefixes
    for pattern in PROCESSOR_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
    # 2. Marketplace prefixes
    for pattern in MARKETPLACE_PREFIXES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
    # 3. Trailing reference tails
    for pattern in REFERENCE_TAILS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
    # 4. Trailing location tokens
    for pattern in LOCATION_TOKENS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
    # 5. Normalize: collapse whitespace, strip
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    # Title-case
    return cleaned.title()

def infer_type(amount: Decimal) -> str:
    """
    Infers transaction type based on amount sign (standard accounting convention).
    Positive = inflow, Negative = outflow.
    """
    if amount > 0:
        return 'income'
    elif amount < 0:
        return 'expense'
    return 'other'
def is_transfer(raw: str) -> bool:
    """Detects if a transaction is likely an internal transfer."""
    if not raw:
        return False
    
    transfer_patterns = [
        r"transfer\b",
        r"internal\b",
        r"withdrawal\b",
        r"deposit\b",
        r"funding\b",
        r"sweep\b"
    ]
    
    raw_lower = raw.lower()
    for pattern in transfer_patterns:
        if re.search(pattern, raw_lower):
            return True
    return False
