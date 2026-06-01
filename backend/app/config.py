import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]
GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OTA_BASE_URL: str = os.getenv("OTA_BASE_URL", "http://localhost:9000")
KB_DIR: str = os.getenv("KB_DIR", "./kb")
CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
