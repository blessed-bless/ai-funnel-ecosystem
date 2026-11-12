from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatTurn:
    role: str
    content: str


class AIProvider(ABC):
    @abstractmethod
    async def reply(self, history: list[ChatTurn], user_message: str) -> str:
        raise NotImplementedError
