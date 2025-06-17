import re
import logging
from typing import Callable, Optional, List, Tuple, Any

logger = logging.getLogger("pysocket.routing")

class Route:
    def __init__(self, pattern: str, callback: Callable):
        try:
            if not isinstance(pattern, str):
                raise ValueError(f"Pattern must be a string, got {type(pattern)}")
            # Normalize pattern to include leading slash
            pattern = pattern.lstrip('^')
            pattern = f'^{pattern.lstrip("/")}'
            self.pattern = re.compile(pattern)
            self.callback = callback
            logger.debug(f"Created Route with pattern {self.pattern.pattern}")
        except re.error as e:
            logger.error(f"Invalid regex pattern {pattern}: {e}")
            raise

class WebSocketRouter:
    def __init__(self):
        self.routes: List[Tuple[re.Pattern, Callable]] = []
        self.logger = logger

    def add_route(self, pattern: str, callback: Callable) -> None:
        try:
            route = Route(pattern, callback)
            self.routes.append((route.pattern, route.callback))
            self.logger.info(f"Added route with pattern {pattern} -> {callback.__name__}")
        except Exception as e:
            self.logger.error(f"Failed to add route with pattern {pattern}: {e}")
            raise

    def resolve(self, path: str) -> Optional[Callable]:
        self.logger.debug(f"Resolving path: {path} (raw: {repr(path)})")
        # Normalize path to remove leading slash for matching
        normalized_path = path.lstrip('/')
        self.logger.debug(f"Normalized path: {normalized_path}")
        for pattern, callback in self.routes:
            self.logger.debug(f"Trying pattern: {pattern.pattern}")
            match = pattern.match(normalized_path)
            self.logger.debug(f"Match result for {normalized_path} against {pattern.pattern}: {match}")
            if match:
                self.logger.info(f"Resolved path {path} to callback {callback.__name__}")
                return callback
        self.logger.warning(f"No route found for path {path}")
        return None