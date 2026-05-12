import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger("connections.nvidia_nim_connection")

class NvidiaNimConnectionError(Exception):
    """Base exception for NVIDIA NIM connection errors"""
    pass

class NvidiaNimConfigurationError(NvidiaNimConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class NvidiaNimAPIError(NvidiaNimConnectionError):
    """Raised when NVIDIA NIM API requests fail"""
    pass

class NvidiaNimConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate NVIDIA NIM configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
            
        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")
            
        return config

    def register_actions(self) -> None:
        """Register available NVIDIA NIM actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", True, str, "System prompt to guide the model"),
                    ActionParameter("model", False, str, "Model to use for generation"),
                    ActionParameter("temperature", False, float, "Randomness in the response"),
                    ActionParameter("max_tokens", False, int, "Maximum tokens to generate")
                ],
                description="Generate text using NVIDIA NIM models"
            ),
            "check-model": Action(
                name="check-model",
                parameters=[
                    ActionParameter("model", True, str, "Model name to check availability")
                ],
                description="Check if a specific model is available"
            ),
            "list-models": Action(
                name="list-models",
                parameters=[],
                description="List available NVIDIA NIM models"
            )
        }

    def _get_client(self) -> OpenAI:
        """Get or create NVIDIA NIM client"""
        if not self._client:
            api_key = os.getenv("NVIDIA_NIM_API_KEY")
            if not api_key:
                raise NvidiaNimConfigurationError("NVIDIA_NIM_API_KEY not found in environment")
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
        return self._client

    def configure(self) -> bool:
        """Sets up NVIDIA NIM API authentication"""
        logger.info("\n🤖 NVIDIA NIM API SETUP")

        if self.is_configured():
            logger.info("\nNVIDIA NIM API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        logger.info("\n📝 To get your NVIDIA NIM API credentials:")
        logger.info("1. Go to https://build.nvidia.com")
        logger.info("2. Select a model and click 'Get API Key'")
        
        api_key = input("\nEnter your NVIDIA NIM API key: ")

        try:
            if not os.path.exists('.env'):
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'NVIDIA_NIM_API_KEY', api_key)
            
            # Validate key
            client = OpenAI(
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
            client.models.list()

            logger.info("\n✅ NVIDIA NIM configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose = False) -> bool:
        """Check if NVIDIA NIM API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv('NVIDIA_NIM_API_KEY')
            if not api_key:
                return False

            client = OpenAI(
                api_key=api_key,
                base_url="https://integrate.api.nvidia.com/v1"
            )
            client.models.list()
            return True
            
        except Exception as e:
            if verbose:
                logger.debug(f"NVIDIA NIM check failed: {e}")
            return False

    def generate_text(self, prompt: str, system_prompt: str, model: str = None, **kwargs) -> str:
        """Generate text using NVIDIA NIM models with parameter cleaning"""
        try:
            client = self._get_client()
            
            if not model:
                model = self.config["model"]

            # Filter out parameters that often cause issues with NVIDIA NIM
            # according to user's past experience (e.g. from Eliza implementation)
            allowed_params = ["temperature", "max_tokens", "top_p", "stream", "stop"]
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_params}

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                **filtered_kwargs
            )

            return completion.choices[0].message.content
            
        except Exception as e:
            raise NvidiaNimAPIError(f"Text generation failed: {e}")

    def check_model(self, model: str, **kwargs) -> bool:
        try:
            client = self._get_client()
            models = client.models.list()
            return any(m.id == model for m in models.data)
        except Exception as e:
            raise NvidiaNimAPIError(f"Model check failed: {e}")

    def list_models(self, **kwargs) -> None:
        try:
            client = self._get_client()
            response = client.models.list().data
            logger.info("\nAVAILABLE NVIDIA NIM MODELS:")
            for i, model in enumerate(response, start=1):
                logger.info(f"{i}. {model.id}")
        except Exception as e:
            raise NvidiaNimAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        load_dotenv()
        if not self.is_configured(verbose=True):
            raise NvidiaNimConfigurationError("NVIDIA NIM is not properly configured")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)
