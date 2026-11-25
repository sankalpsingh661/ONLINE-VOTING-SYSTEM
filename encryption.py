from cryptography.fernet import Fernet
from pathlib import Path
import hashlib

KEY_FILE = Path(__file__).parent / "secret.key"

if KEY_FILE.exists():
    key = KEY_FILE.read_bytes()
else:
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)

cipher = Fernet(key)


def encrypt_vote(vote_text):
    """Encrypt a vote string using Fernet symmetric encryption."""
    return cipher.encrypt(vote_text.encode("utf-8"))


def decrypt_vote(encrypted_text):
    """Decrypt an encrypted vote back to plaintext."""
    if isinstance(encrypted_text, str):
        encrypted_text = encrypted_text.encode("utf-8")
    return cipher.decrypt(encrypted_text).decode("utf-8")


def hash_vote(voter_id, candidate_id, position_id):
    """Create a SHA-256 hash of a vote for verification/audit."""
    data = f"{voter_id}:{candidate_id}:{position_id}"
    return hashlib.sha256(data.encode()).hexdigest()
