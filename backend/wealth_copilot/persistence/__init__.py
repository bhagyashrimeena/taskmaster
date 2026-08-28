"""Optional persistence adapters for product state."""

from .firestore import firestore_persistence

__all__ = ["firestore_persistence"]
