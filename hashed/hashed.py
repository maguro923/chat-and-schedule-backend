import asyncio
import argon2
from argon2 import PasswordHasher

def generate_hash(password: str, salt: str):
    ph = PasswordHasher(
        memory_cost=47104,
        time_cost=5,
        parallelism=1,
        hash_len=256
    )
    try:
        hash = ph.hash(password, salt=bytes.fromhex(salt))
        return hash
    except argon2.exceptions.HashingError:
        print("Error hashing password")
        return None
    except Exception as e:
        print(f"Error hashing password: {e}")
        return None

def verify_pw(password: str, hash: str, salt: str) -> bool:
    ph = PasswordHasher(
        memory_cost=47104,
        time_cost=5,
        parallelism=1,
        hash_len=256
    )
    try:
        sended_hash = ph.hash(password, salt=bytes.fromhex(salt))
        if sended_hash == hash:
            return True
        else:
            raise argon2.exceptions.VerificationError
    except argon2.exceptions.VerificationError:
        print("Error verifying password")
        return False
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False