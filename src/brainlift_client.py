import logging
import time

import requests
from os import environ
from typing import Optional

from .oauth_client import OAuthClient


logger = logging.getLogger(__name__)


class _SupabaseTokenManager:
    def __init__(
        self,
        oauth_client: OAuthClient,
        supabase_url: Optional[str],
        supabase_anon_key: Optional[str],
    ):
        self.oauth_client = oauth_client
        self.supabase_url = (supabase_url or "").rstrip("/")
        self.supabase_anon_key = supabase_anon_key
        self._access_token: Optional[str] = None
        self._expires_at: Optional[float] = None
        self._user_id: Optional[str] = None

        if not self.supabase_url or not self.supabase_anon_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY environment variables must be set"
            )

    def get_token(self) -> str:
        """
        Get a cached Supabase access token, refreshing from Google credentials when
        missing or expired.
        """
        now = time.time()

        if self._access_token and self._expires_at and now < self._expires_at:
            print(
                "Using cached Supabase access token (expires_at=%s)", self._expires_at
            )
            return self._access_token

        logger.info("Fetching new Supabase access token using Google credentials")
        access_token, expires_at = self._exchange_google_token_for_supabase()
        self._access_token = access_token
        self._expires_at = expires_at

        logger.debug(
            "Obtained new Supabase access token; expires_at=%s has_expiry=%s",
            self._expires_at,
            self._expires_at is not None,
        )

        return self._access_token

    def invalidate(self) -> None:
        """Invalidate the cached Supabase token so it is fetched again next time."""
        logger.info("Invalidating cached Supabase access token")
        self._access_token = None
        self._expires_at = None

    def _exchange_google_token_for_supabase(self) -> tuple[str, Optional[float]]:
        """
        Exchange Google OAuth token for a Supabase access token via the Supabase
        auth/token endpoint.
        """
        credentials = self.oauth_client.get_credentials()
        if not credentials:
            raise ValueError(
                "Failed to get Google OAuth credentials for Supabase token exchange"
            )

        id_token = getattr(credentials, "id_token", None)
        if not id_token:
            # Fallback for flows that don't populate id_token explicitly.
            logger.warning(
                "Google credentials did not include id_token; falling back to "
                "access token for Supabase exchange"
            )
            id_token = credentials.token

        url = f"{self.supabase_url}/auth/v1/token?grant_type=id_token"
        headers = {
            "apikey": self.supabase_anon_key,
            "Content-Type": "application/json",
        }
        payload = {
            "id_token": id_token,
            "provider": "google",
        }

        logger.debug(
            "Exchanging Google token for Supabase token at %s (payload keys=%s)",
            url,
            list(payload.keys()),
        )

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Error exchanging Google token for Supabase token: %s",
                exc,
                exc_info=True,
            )
            raise

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            logger.error("Supabase auth response missing access_token: %s", data)
            raise ValueError("Supabase auth response missing access_token")

        # Capture the Supabase user ID from the auth response so we can scope
        # subsequent REST queries to the current user.
        user = data.get("user") or {}
        self._user_id = user.get("id")
        logger.debug("Supabase auth user id: %s", self._user_id)

        expires_in = data.get("expires_in")
        expires_at: Optional[float] = None
        if isinstance(expires_in, (int, float)):
            # Refresh 60 seconds before expiry to avoid edge cases.
            expires_at = time.time() + float(expires_in) - 60
        return access_token, expires_at

    def get_user_id(self) -> str:
        """
        Get the Supabase user ID associated with the current access token.

        Ensures we've gone through the token exchange flow at least once so
        that the user id is populated from the auth response.
        """
        if self._user_id:
            logger.debug("Using cached Supabase user id: %s", self._user_id)
            return self._user_id

        # Trigger token exchange if needed to populate user id.
        logger.info(
            "Supabase user id not yet cached; fetching new Supabase token to obtain it"
        )
        self.get_token()

        if not self._user_id:
            raise ValueError("Supabase auth response did not include user.id")

        logger.debug(
            "Obtained Supabase user id after token exchange: %s", self._user_id
        )
        return self._user_id


_supabase_token_manager: Optional[_SupabaseTokenManager] = None


def _get_supabase_token_manager(oauth_client: OAuthClient) -> _SupabaseTokenManager:
    """
    Get the singleton Supabase token manager instance for this process.
    """
    global _supabase_token_manager

    if _supabase_token_manager is None:
        supabase_url = environ.get("SUPABASE_URL")
        supabase_anon_key = environ.get("SUPABASE_ANON_KEY")

        logger.debug(
            "Initializing SupabaseTokenManager with url=%s anon_key_present=%s",
            supabase_url,
            bool(supabase_anon_key),
        )

        _supabase_token_manager = _SupabaseTokenManager(
            oauth_client=oauth_client,
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
        )

    return _supabase_token_manager


class BrainliftClient:
    def __init__(self, api_url: str, oauth_client: Optional[OAuthClient] = None):
        """
        Initialize Brainlift API client with OAuth authentication.

        Args:
            api_url: Base URL for the Brainlift API
            oauth_client: Optional OAuthClient instance (will create one if not provided)
        """
        self.base_url = api_url
        self.oauth_client = oauth_client or OAuthClient()
        self.supabase_anon_key = environ.get("SUPABASE_ANON_KEY")

    def _get_headers(self) -> dict:
        """
        Get authentication headers for API requests.

        Returns:
            Dictionary of headers with Supabase bearer token
        """
        manager = _get_supabase_token_manager(self.oauth_client)
        token = manager.get_token()
        if not token:
            raise ValueError("Failed to get Supabase access token")

        logger.debug("Returning Authorization header with Supabase bearer token")
        return {
            "Authorization": f"Bearer {token}",
            "apikey": self.supabase_anon_key,
        }

    def _get_auth_context(self) -> tuple[dict, str]:
        """
        Get headers and the current Supabase user id for authenticated requests.
        """
        manager = _get_supabase_token_manager(self.oauth_client)
        token = manager.get_token()
        if not token:
            raise ValueError("Failed to get Supabase access token")

        user_id = manager.get_user_id()
        if not user_id:
            raise ValueError("Failed to determine Supabase user id from auth response")

        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": self.supabase_anon_key,
        }

        logger.debug(
            "Prepared Supabase auth context with user_id=%s base_url=%s",
            user_id,
            self.base_url,
        )
        return headers, user_id

    def get_brainlifts(self):
        """
        GET `/brainlifts` → 200 [{ id, title, qualityScore, createdAt, updatedAt }]
        """

        try:
            headers, user_id = self._get_auth_context()
            params = {
                "select": "*",
                "user_id": f"eq.{user_id}",
                "order": "updated_at.desc",
            }

            logger.info(
                "Fetching BrainLifts for Supabase user_id=%s with params=%s",
                user_id,
                params,
            )

            response = requests.get(
                f"{self.base_url}/rest/v1/brainlifts",
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error fetching BrainLifts: {e}")
        except requests.exceptions.ConnectionError as e:
            raise Exception(
                f"Failed to connect to BrainLift API at {self.base_url}: {e}"
            )
        except requests.exceptions.Timeout:
            raise Exception("Request timed out after 30 seconds")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching BrainLifts: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")

    def get_brainlift(self, brainlift_id: str):
        """
        GET `/brainlifts/{brainliftId}` → 200 { id, title, qualityScore, dokDistribution, stats }
        """

        try:
            # Use the same Edge Function route as the frontend application so we
            # benefit from the same ownership checks and response semantics.
            headers = self._get_headers()
            response = requests.get(
                f"{self.base_url}/functions/v1/api/v1/brainlifts/{brainlift_id}",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                raise Exception(f"BrainLift with ID '{brainlift_id}' not found")
            if status == 403:
                raise Exception(
                    f"Forbidden from accessing BrainLift '{brainlift_id}' (ownership check failed)"
                )
            raise Exception(
                f"HTTP error fetching BrainLift '{brainlift_id}' via Edge Function: {e}"
            )
        except requests.exceptions.ConnectionError as e:
            raise Exception(
                f"Failed to connect to BrainLift API at {self.base_url}: {e}"
            )
        except requests.exceptions.Timeout:
            raise Exception("Request timed out after 30 seconds")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching BrainLift '{brainlift_id}': {e}")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")

    def get_nodes(self, brainlift_id: str):
        """
        GET `/brainlifts/{brainliftId}/nodes` → 200 [{ id, parentId|null, position, dokLevel, content, status, rowVersion }]
        """

        try:
            headers = self._get_headers()
            response = requests.get(
                f"{self.base_url}/functions/v1/api/v1/brainlifts/{brainlift_id}/nodes",
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                raise Exception(
                    f"Nodes for BrainLift with ID '{brainlift_id}' not found"
                )
            if status == 403:
                raise Exception(
                    f"Forbidden from accessing nodes for BrainLift '{brainlift_id}' (ownership check failed)"
                )
            raise Exception(
                f"HTTP error fetching nodes for BrainLift '{brainlift_id}' via Edge Function: {e}"
            )
        except requests.exceptions.ConnectionError as e:
            raise Exception(
                f"Failed to connect to BrainLift API at {self.base_url}: {e}"
            )
        except requests.exceptions.Timeout:
            raise Exception("Request timed out after 30 seconds")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching nodes for BrainLift '{brainlift_id}': {e}")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")
