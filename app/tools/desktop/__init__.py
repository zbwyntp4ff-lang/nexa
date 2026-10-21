"""Desktop / OS capability surface for NEXA.

Honest inventory: only tools that exist and return confirmed results are listed
as available. Unimplemented capabilities refuse rather than invent success.
"""
from app.tools.desktop.browser_tool import BrowserTool
from app.tools.desktop.capabilities import DesktopCapabilityReport, audit_desktop_capabilities
from app.tools.desktop.local_files import LocalFileTool
from app.tools.desktop.open_result import OpenResultTool

__all__ = [
    "BrowserTool",
    "LocalFileTool",
    "OpenResultTool",
    "DesktopCapabilityReport",
    "audit_desktop_capabilities",
]
