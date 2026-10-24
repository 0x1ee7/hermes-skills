"""End-to-end check of the Blender MCP chain: MCP client -> mcp-for-blender (stdio) -> addon.

Run with the Python of the mcp-for-blender uv tool (it ships the `mcp` package):
    <uv tool dir>/mcp-for-blender/Scripts/python.exe mcp_smoke.py
Blender's window must be open with the addon enabled (its server starts with the GUI).
"""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

SERVER = os.environ.get("MCP_FOR_BLENDER", os.path.expanduser("~/.local/bin/mcp-for-blender.exe"))


async def main() -> int:
    env = get_default_environment()
    env.update({"DISABLE_TELEMETRY": "true", "BLENDER_HOST": "localhost", "BLENDER_PORT": "9876"})
    params = StdioServerParameters(command=SERVER, args=[], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", sorted(t.name for t in tools.tools))
            status = await session.call_tool("get_addon_status", {})
            print("get_addon_status:", status.content[0].text[:300] if status.content else status)
            code = "import bpy\nprint(sorted(o.name for o in bpy.data.objects), bpy.app.version_string)"
            result = await session.call_tool("execute_blender_code", {"code": code})
            print("execute_blender_code:", result.content[0].text[:300] if result.content else result)
            # `look` takes mode="angles" with views=[...] (front, back, left, right, top,
            # three_quarter) and returns an image content item.
            return 1 if result.isError or status.isError else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
