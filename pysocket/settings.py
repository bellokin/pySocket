from typing import List, Callable

class Settings:
    HOST: str = "localhost"
    PORT: int = 8765
    PING_INTERVAL: int = 20
    MIDDLEWARE: List[Callable] = []

settings = Settings()