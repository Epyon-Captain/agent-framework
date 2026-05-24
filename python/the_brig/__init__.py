"""
The Brig - Agent Containment System
====================================
Aboard the Epyon, agents who misbehave get thrown in The Brig.
They stay locked up for a set sentence duration and are released
only when their time is served.
"""

from .brig import TheBrig, BrigCell, Brigoffense

__all__ = ["TheBrig", "BrigCell", "Brigoffense"]
