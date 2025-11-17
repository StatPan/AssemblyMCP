"""
AssemblyMCP - MCP Server for Korean National Assembly Open API
"""

from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("AssemblyMCP")


@mcp.tool()
async def get_assembly_info() -> str:
    """
    Get basic information about the Korean National Assembly API.

    Returns:
        Information about available API endpoints
    """
    return "Korean National Assembly Open API MCP Server - Ready to implement API tools"


def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
