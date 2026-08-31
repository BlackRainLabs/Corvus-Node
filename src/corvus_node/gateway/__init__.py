"""Gateway package. Identity adapters on Node, not in the guest.

Organization: Black Rain Labs
Division: Research & Development Division
"""

from corvus_node.gateway.adapter import ChannelAdapter, LocalCliAdapter

__all__ = ["ChannelAdapter", "LocalCliAdapter"]
