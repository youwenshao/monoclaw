"""Abstract base class for messaging providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class IncomingMessage:
    sender: str
    text: str
    media_url: str | None = None
    media_type: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    to: str
    text: str
    media_urls: list[str] = field(default_factory=list)


class MessagingProvider(ABC):
    """Interface for send/receive messaging."""

    @abstractmethod
    async def send_text(self, to: str, text: str) -> str:
        """Send a text message. Returns a message SID or ID."""
        ...

    @abstractmethod
    async def send_media(self, to: str, text: str, media_urls: list[str]) -> str:
        """Send a message with media attachments."""
        ...

    @abstractmethod
    def parse_webhook(self, data: dict) -> IncomingMessage:
        """Parse an incoming webhook payload into an IncomingMessage."""
        ...
