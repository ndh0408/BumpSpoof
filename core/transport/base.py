"""
base.py — transport interface.

A transport knows how to deliver a single GPS fix to one device and how to
open/close that channel. The playback engine only talks to this interface.
"""

from abc import ABC, abstractmethod


class BaseTransport(ABC):
    name = "base"

    @abstractmethod
    def connect(self) -> bool:
        """Open the channel. Return True on success."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the channel and restore the device's real GPS."""

    @abstractmethod
    def send_location(
        self,
        lat: float,
        lon: float,
        alt: float = 12.0,
        accuracy: float = 8.0,
        bearing: float = 0.0,
        speed: float = 0.0,
    ) -> bool:
        """Push one fix. Return True on success, False if the link dropped."""

    def status(self) -> str:
        """Human-readable connection status / last error."""
        return ""
