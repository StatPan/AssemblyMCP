"""MCP Server for Korean National Assembly API"""

from fastmcp import FastMCP

from assemblymcp.settings import settings

# Initialize FastMCP server
mcp = FastMCP("AssemblyMCP")


@mcp.tool()
async def get_assembly_info() -> str:
    """
    Get basic information about the Korean National Assembly API.

    Returns:
        Information about available API endpoints and configuration status
    """
    api_key_status = "configured" if settings.assembly_api_key else "not configured"
    return f"Korean National Assembly Open API MCP Server\nAPI Key: {api_key_status}"


def main():
    """Run the MCP server"""
    # Validate settings on startup (but don't fail if API key is missing yet)
    if settings.assembly_api_key:
        print(f"[OK] API key configured: {settings.assembly_api_key[:8]}...")
    else:
        print("[WARNING] API key not configured. Set ASSEMBLY_API_KEY environment variable.")

    mcp.run()


if __name__ == "__main__":
    main()
