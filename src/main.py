#!/usr/bin/env python3
from src.server import mcp


def main():
    """Run the FastMCP server in STDIO mode"""
    # Force STDIO mode for MCP Inspector compatibility
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
