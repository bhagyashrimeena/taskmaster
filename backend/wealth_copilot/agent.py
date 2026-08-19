"""ADK discovery module.

ADK finds this module when ``adk run wealth_copilot`` is executed from the
``backend`` directory. The exported name must remain ``root_agent``.
"""

from .agents.taskmaster import root_agent

__all__ = ["root_agent"]

