import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.comfy_api_connection")

class ComfyAPIConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return config

    def register_actions(self) -> None:
        self.actions = {
            "generate-image": Action(
                name="generate-image",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for image generation")
                ],
                description="Generate image using ComfyUI"
            )
        }

    def configure(self, **kwargs) -> bool:
        """Sets up ComfyUI API URL"""
        try:
            server_url = kwargs.get("server_url")
            if server_url:
                set_key(".env", "COMFYUI_API_URL", server_url)
                return True
            return False
        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        load_dotenv()
        return os.getenv("COMFYUI_API_URL") is not None
