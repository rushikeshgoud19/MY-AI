from abc import ABC, abstractmethod
from typing import Any, Optional
import logging

class BaseAgent(ABC):
    """
    Abstract Base Class for all Mizune's specialized agents.
    Each agent should handle a specific domain of Master's requests.
    """
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def execute(self, task_input: str, context: Optional[dict] = None) -> Any:
        """
        Execute the agent's core logic.
        :param task_input: The request or command from the Manager.
        :param context: Additional metadata or state needed for the task.
        :return: The result of the operation.
        """
        pass

    def log(self, message: str):
        self.logger.info(message)
        print(f'[{self.__class__.__name__}] {message}')
