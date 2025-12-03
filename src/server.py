import logging
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src.brainlift_client import BrainliftClient
from src.oauth_client import OAuthClient

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("brainlift-mcp")

# Initialize BrainliftClient with OAuth authentication
API_URL = os.environ.get("SUPABASE_URL")
if API_URL is None:
    raise Exception("SUPABASE_URL environment variable is not set")

oauth_client = OAuthClient()
client = BrainliftClient(api_url=API_URL, oauth_client=oauth_client)


@mcp.tool()
def get_brainlifts() -> list[dict]:
    """
    Get an overview of the user's BrainLifts. This is used by the agent to know
    the user's BrainLift topics and quality scores to focus on improving lower
    quality BrainLifts.

    Returns:
        A list of BrainLifts with id, title, and qualityScore
        [{ id, title, qualityScore }]
    """
    try:
        return client.get_brainlifts()
    except Exception as e:
        raise Exception(f"Failed to get BrainLifts: {str(e)}")


@mcp.tool()
def get_brainlift_info(brainlift_id: str) -> dict:
    """
    Get the content of the user's BrainLift. Also get the statistics about the BrainLift.

    Args:
        brainlift_id: The ID of the BrainLift to get info for

    Returns:
        A dictionary containing:
        {
            "brainlift_title": string,
            "stats": {
                "created_at": string,
                "updated_at": string,
                "quality_score": int,
                "quality_dimensions: {
                    "gaps": int,
                    "spiky_pov": int,
                    "consistent": int,
                    "topic_focus": int,
                    "dok_coverage": int,
                    "digest_quality": int,
                    "link_discipline": int
                },
                "visibility": string,
            }
            "brainlift_contents": string
        }
    """
    try:
        if not brainlift_id:
            raise Exception("brainlift_id parameter is required")

        brainlift_data = client.get_brainlift(brainlift_id)
        nodes = client.get_nodes(brainlift_id)
        # print(f"Received {len(nodes)} nodes, first node: {nodes[0]}")
        # print(f"Brainlift data: {brainlift_data}")

        # Format the response according to the specification
        return {
            "brainlift_title": brainlift_data.get("title", ""),
            "stats": {
                "created_at": brainlift_data.get("created_at", ""),
                "updated_at": brainlift_data.get("updated_at", ""),
                "quality_score": brainlift_data.get("quality_score", ""),
                "quality_dimensions": brainlift_data.get("quality_dimensions", {}),
                "visibility": brainlift_data.get("visibility", ""),
            },
            "brainlift_contents": "\n".join(
                [
                    f"DoK Level {node.get('dok_level', 'Not Found')}: {node.get('content', '')}"
                    for node in nodes
                ]
            ),
        }
    except Exception as e:
        raise Exception(f"Failed to get BrainLift info: {str(e)}")


# @mcp.tool()
def get_brainlift_doks(brainlift_id: str, dok_levels: list[int]) -> dict:
    """
    Get the DOK 1, 2, 3, or 4 nodes from a BrainLift. This is useful for agents
    to confirm that their recommendation is relevant to the BrainLift, and that
    the same/similar information is not already present.

    Args:
        brainlift_id: The ID of the BrainLift to get DOK nodes for
        dok_levels: A list of DOK levels to retrieve (e.g., [1, 2, 3, 4])

    Returns:
        A dictionary containing:
        {
            "brainlift_title": string,
            "dok1": [string],
            "dok2": [string],
            "dok3": [string],
            "dok4": [string]
        }
    """
    try:
        if not brainlift_id:
            raise Exception("brainlift_id parameter is required")

        if not dok_levels:
            raise Exception("dok_levels parameter is required")

        # Validate DOK levels
        invalid_levels = [level for level in dok_levels if level not in [1, 2, 3, 4]]
        if invalid_levels:
            raise Exception(
                f"Invalid DOK levels: {invalid_levels}. Must be 1, 2, 3, or 4"
            )

        brainlift_data = client.get_brainlift(brainlift_id)
        nodes = client.get_nodes(brainlift_id)

        # Filter nodes by DOK levels
        result = {"brainlift_title": brainlift_data.get("title", "")}

        for level in dok_levels:
            dok_key = f"dok{level}"
            filtered_nodes = [
                node.get("content", "")
                for node in nodes
                if node.get("dok_level") == level
            ]
            result[dok_key] = filtered_nodes

        return result
    except Exception as e:
        raise Exception(f"Failed to get BrainLift DOK nodes: {str(e)}")


def main() -> None:
    """Main entry point for the BrainLift MCP server."""
    logger.info("Starting BrainLift MCP server in stdio mode")
    # Force STDIO mode for MCP Inspector compatibility
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
