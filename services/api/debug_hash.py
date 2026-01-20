from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
try:
    print(f"Hashing 'admin'...")
    h = pwd_context.hash("admin")
    print(f"Success: {h}")
    print(f"Verifying 'admin'...")
    print(pwd_context.verify("admin", h))
except Exception as e:
    print(f"Error: {e}")
