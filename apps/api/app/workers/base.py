"""
Abstract base for pipeline steps.

Real implementations will call ComfyUI API on GPU instances.
Mock implementations simulate processing for local dev.
"""

from abc import ABC, abstractmethod
from typing import Any


class PipelineStep(ABC):
    """Base class for all pipeline stage workers."""

    @abstractmethod
    async def execute(self, **kwargs) -> dict[str, Any]:
        """Execute the pipeline step. Returns artifact metadata dict."""
        ...
