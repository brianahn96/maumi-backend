import hashlib
from uuid_utils import uuid7

def create_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

def uuid7_generator():
    return uuid7()