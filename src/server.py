import os
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to the path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from brainlift_client import BrainliftClient
from oauth_client import OAuthClient

# Initialize FastMCP server
mcp = FastMCP("brainlift-mcp")

# Initialize BrainliftClient with OAuth authentication
API_URL = os.environ.get("BRAINLIFT_API_URL", "https://api.brainlift.com")
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
    return client.get_brainlifts()


@mcp.tool()
def get_brainlift_info(brainlift_id: str) -> dict:
    """
    Get statistics about the user's BrainLift. Used to check the completeness 
    of a BrainLift. Also used to check how old it is and when it was last updated.
    The age and lastUpdated fields are relative to the current time (X days ago) 
    as opposed to a time string.
    
    Args:
        brainlift_id: The ID of the BrainLift to get info for
    
    Returns:
        A dictionary containing:
        {
            "brainlift_title": string,
            "dok_distribution": { d1: int, d2: int, d3: int, d4: int },
            "stats": {
                nodeCount: int,
                age: string,
                lastUpdated: string
            },
            "brainlift_contents": string
        }
    """
    brainlift_data = client.get_brainlift(brainlift_id)
    nodes = client.get_nodes(brainlift_id)
    
    # Format the response according to the specification
    return {
        "brainlift_title": brainlift_data.get("title", ""),
        "dok_distribution": brainlift_data.get("dokDistribution", {}),
        "stats": brainlift_data.get("stats", {}),
        "brainlift_contents": "\n".join([node.get("content", "") for node in nodes])
    }


@mcp.tool()
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
    brainlift_data = client.get_brainlift(brainlift_id)
    nodes = client.get_nodes(brainlift_id)
    
    # Filter nodes by DOK levels
    result = {
        "brainlift_title": brainlift_data.get("title", "")
    }
    
    for level in dok_levels:
        dok_key = f"dok{level}"
        filtered_nodes = [
            node.get("content", "") 
            for node in nodes 
            if node.get("dokLevel") == level
        ]
        result[dok_key] = filtered_nodes
    
    return result

