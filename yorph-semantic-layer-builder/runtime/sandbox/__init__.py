"""
Sandbox package — subprocess-based Python execution for agent validation.

Provides a secure environment where agents can run arbitrary pandas/numpy/scipy
analysis against cached sample data without network or filesystem access.
"""

from runtime.sandbox.runner import SandboxRunner, SandboxResult

__all__ = ["SandboxRunner", "SandboxResult"]
