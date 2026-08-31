"""Engine 3 must not grow a tool path.

Organization: Black Rain Labs
Division: Research & Development Division
"""

import inspect

from corvus_node.runtime.engines import Engine3


def test_engine3_has_no_tool_surface() -> None:
    assert not hasattr(Engine3, "run_tool")
    source = inspect.getsource(Engine3)
    assert "echo_run" not in source
    assert "tool_call" not in source
