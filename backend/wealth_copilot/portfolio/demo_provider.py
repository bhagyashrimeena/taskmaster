"""Backward-compatible import for the renamed simulated provider."""

from .simulated_provider import SimulatedPortfolioProvider


DemoPortfolioProvider = SimulatedPortfolioProvider

__all__ = ["DemoPortfolioProvider", "SimulatedPortfolioProvider"]
