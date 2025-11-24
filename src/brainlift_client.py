import requests
from os import environ
from typing import Optional
from .oauth_client import OAuthClient


class BrainliftClient:
    def __init__(
        self, 
        api_url: str,
        oauth_client: Optional[OAuthClient] = None
    ):
        """
        Initialize Brainlift API client with OAuth authentication.
        
        Args:
            api_url: Base URL for the Brainlift API
            oauth_client: Optional OAuthClient instance (will create one if not provided)
        """
        self.base_url = api_url
        self.DEMO_MODE = environ.get("DEMO_MODE", "false").lower() == "true"
        self.oauth_client = oauth_client or OAuthClient()
    
    def _get_headers(self) -> dict:
        """
        Get authentication headers for API requests.
        
        Returns:
            Dictionary of headers with OAuth bearer token
        """
        token = self.oauth_client.get_access_token()
        if not token:
            raise ValueError("Failed to get OAuth access token")
        return {"Authorization": f"Bearer {token}"}

    def get_brainlifts(self):
        """
        GET `/brainlifts` → 200 [{ id, title, qualityScore, createdAt, updatedAt }]
        """
        
        if self.DEMO_MODE:
            return [
                {
                    "id": "123",
                    "title": "Demo Brainlift",
                    "qualityScore": 0.9,
                    "createdAt": "2021-01-01",
                    "updatedAt": "2021-01-01"
                },
                {
                    "id": "456",
                    "title": "Demo Brainlift 2",
                    "qualityScore": 0.8,
                    "createdAt": "2021-01-01",
                    "updatedAt": "2021-01-01"
                }
            ]
        
        headers = self._get_headers()
        response = requests.get(f"{self.base_url}/brainlifts", headers=headers)
        return response.json()

    def get_brainlift(self, brainlift_id: str):
        """
        GET `/brainlifts/{brainliftId}` → 200 { id, title, qualityScore, dokDistribution, stats }
        """
        
        if self.DEMO_MODE:
            return {
                "id": "123",
                "title": "Demo Brainlift",
                "qualityScore": 0.9,
                "dokDistribution": {
                    "1": 10,
                },
                "stats": {
                    "totalNodes": 100,
                }
            }
        
        headers = self._get_headers()
        response = requests.get(f"{self.base_url}/brainlifts/{brainlift_id}", headers=headers)
        return response.json()

    def get_nodes(self, brainlift_id: str):
        """
        GET `/brainlifts/{brainliftId}/nodes` → 200 [{ id, parentId|null, position, dokLevel, content, status, rowVersion }]
        """

        if self.DEMO_MODE:
            return [
                {
                    "id": "123",
                    "parentId": None,
                    "position": 0,
                    "dokLevel": 1,
                    "content": "Demo Node",
                },
                {
                    "id": "456",
                    "parentId": "123",
                    "position": 1,
                    "dokLevel": 2,
                    "content": "Demo Node 2",
                }
            ]
        
        headers = self._get_headers()
        response = requests.get(f"{self.base_url}/brainlifts/{brainlift_id}/nodes", headers=headers)
        return response.json()