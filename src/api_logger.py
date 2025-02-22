import os
import json
from datetime import datetime
from typing import Any, Dict

class APILogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self._ensure_log_dir()

    def _ensure_log_dir(self):
        """Ensure the log directory exists."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def log_api_error(self, endpoint: str, status_code: int, response_text: str, 
                     params: Dict[str, Any] = None, headers: Dict[str, Any] = None):
        """Log API errors to a file with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"steam_api_error_{timestamp}.log"
        filepath = os.path.join(self.log_dir, filename)

        error_data = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "status_code": status_code,
            "response": response_text,
            "request_params": params,
            "request_headers": headers
        }

        with open(filepath, 'w') as f:
            json.dump(error_data, f, indent=2)
