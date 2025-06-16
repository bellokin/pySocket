import re
import logging
from typing import Callable, Optional, List, Tuple, Any

logger = logging.getLogger("pysocket.routing")

class Route:
    def __init__(self, pattern: str, callback: Callable):
        try:
            if not isinstance(pattern, str):
                raise ValueError(f"Pattern must be a string, got {type(pattern)}")
            # Add ^ and make trailing slash optional
            pattern = pattern if pattern.startswith('^') else f'^{pattern}'
            pattern = pattern.rstrip('$')  # Remove $ if present
            pattern = f'{pattern.rstrip("/")}/?$'  # Make trailing slash optional
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
        self.logger.debug(f"Resolving path: {path}")
        for pattern, callback in self.routes:
            self.logger.debug(f"Trying pattern: {pattern.pattern}")
            match = pattern.match(path)
            if match:
                self.logger.info(f"Resolved path {path} to callback {callback.__name__}")
                return callback
        self.logger.warning(f"No route found for path {path}")
        return None