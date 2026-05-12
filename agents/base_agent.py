from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging


class BaseAgent(ABC):
    """
    Abstract Base Class for all Mizune's specialized agents.

    Each agent should handle a specific domain of Master's requests.
    Provides common logging and configuration access.

    Attributes:
        config: Configuration dictionary loaded from config.json
        logger: Logger instance for the agent
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the base agent.

        Args:
            config: Configuration dictionary from config.json
        """
        self.config: Dict[str, Any] = config
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(self, task_input: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute the agent's core logic.

        Args:
            task_input: The request or command from the ManagerAgent
            context: Additional metadata or state needed for the task

        Returns:
            The result of the operation (varies by agent implementation)
        """
        pass

    def log(self, message: str) -> None:
        """
        Log a message to both logger and stdout.

        Args:
            message: The message to log
        """
        self.logger.info(message)
        print(f'[{self.__class__.__name__}] {message}')
