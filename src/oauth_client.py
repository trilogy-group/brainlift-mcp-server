import os
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import]
from google.auth.transport.requests import Request


class OAuthClient:
    """Handles OAuth 2.0 authentication flow and token management."""

    def __init__(
        self,
        client_secrets_path: str | None = None,
        token_path: str | None = None,
        scopes: list[str] | None = None,
    ):
        """
        Initialize OAuth client with environment variables or provided paths.

        Args:
            client_secrets_path: Path to client secrets JSON file
            token_path: Path to store/retrieve OAuth tokens
            scopes: OAuth scopes to request
        """
        self.client_secrets_path = client_secrets_path or os.environ.get(
            "OAUTH_CLIENT_SECRET_PATH", "./credentials/client-secrets.json"
        )
        self.token_path = token_path or os.environ.get(
            "OAUTH_CLIENT_TOKEN_PATH", "./.gcp-saved-token.json"
        )
        self.scopes = scopes or [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]
        self.credentials: Credentials | None = None

    def get_credentials(self) -> Credentials | None:
        """
        Get valid OAuth credentials, refreshing if necessary.

        Returns:
            Valid Credentials object or None if authentication fails
        """
        # Try to load existing credentials
        if self.token_path and os.path.exists(self.token_path):
            try:
                with open(self.token_path, "r") as token_file:
                    token_data = json.load(token_file)
                    self.credentials = Credentials.from_authorized_user_info(
                        token_data, self.scopes
                    )
                    # NOTE: google.oauth2.credentials.Credentials.from_authorized_user_info
                    # does not restore id_token from the file, even if present. If we
                    # have an id_token saved, manually reattach it to the private
                    # attribute so `credentials.id_token` works.
                    if self.credentials:
                        saved_id_token = token_data.get("id_token")
                        if saved_id_token:
                            setattr(self.credentials, "_id_token", saved_id_token)
            except Exception as e:
                print(f"Error loading credentials: {e}")
                self.credentials = None

        # Refresh credentials if expired
        if (
            self.credentials
            and self.credentials.expired
            and self.credentials.refresh_token
        ):
            try:
                self.credentials.refresh(Request())
                self._save_credentials()
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                self.credentials = None

        # Start new OAuth flow if no valid credentials
        if not self.credentials or not self.credentials.valid:
            print(
                "No valid credentials, running OAuth flow",
                self.credentials,
                self.credentials.valid if self.credentials else None,
            )
            self.credentials = self._run_oauth_flow()

        return self.credentials

    def _run_oauth_flow(self) -> Credentials | None:
        """
        Run the OAuth 2.0 authorization flow.

        Returns:
            Credentials object or None if flow fails
        """
        if self.client_secrets_path and not os.path.exists(self.client_secrets_path):
            print(f"Client secrets file not found: {self.client_secrets_path}")
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_path, scopes=self.scopes
            )

            # Run local server flow on a fixed port so redirect_uri can be registered
            # in the Google Cloud Console (e.g., http://localhost:8080/).
            credentials = flow.run_local_server(
                port=8080,
                authorization_prompt_message="Please visit this URL to authorize: {url}",
                success_message="Authorization successful! You may close this window.",
                open_browser=True,
            )
            print(f"OAuth flow successful: {credentials.to_json()}")

            self._save_credentials(credentials)
            return credentials

        except Exception as e:
            print(f"OAuth flow failed: {e}")
            return None

    def _save_credentials(self, credentials: Credentials | None = None):
        """
        Save credentials to token file.

        Args:
            credentials: Credentials to save (uses self.credentials if not provided)
        """
        creds = credentials or self.credentials
        if not creds:
            return

        try:
            # Ensure directory exists
            token_dir = self.token_path and os.path.dirname(self.token_path)
            if token_dir:
                Path(token_dir).mkdir(parents=True, exist_ok=True)

            # Save credentials, including expiry, in a format compatible with
            # Credentials.from_authorized_user_info. That helper expects an
            # "authorized_user" style dict with a refresh_token field present,
            # even if it's null.
            token_data = {
                **json.loads(creds.to_json()),
            }
            # Ensure required fields exist for authorized_user format.
            if "refresh_token" not in token_data:
                token_data["refresh_token"] = getattr(creds, "refresh_token", None)
            token_data["id_token"] = getattr(creds, "id_token", None)
            token_data["type"] = "authorized_user"

            if not self.token_path:
                raise ValueError("Token path is not set")

            with open(self.token_path, "w") as token_file:
                json.dump(token_data, token_file, indent=2)

        except Exception as e:
            print(f"Error saving credentials: {e}")

    def get_access_token(self) -> str | None:
        """
        Get the current access token, refreshing if necessary.

        Returns:
            Access token string or None if unavailable
        """
        credentials = self.get_credentials()
        print(f"Credentials: {credentials.to_json() if credentials else None}")
        return credentials.token if credentials else None

    def revoke_credentials(self):
        """Revoke and delete stored credentials."""
        if self.credentials:
            try:
                self.credentials.revoke(Request())
            except Exception as e:
                print(f"Error revoking credentials: {e}")

        # Delete token file
        if os.path.exists(self.token_path):
            os.remove(self.token_path)

        self.credentials = None


def cli():
    """CLI entry point for OAuth authentication."""
    import sys

    client = OAuthClient()

    if len(sys.argv) > 1 and sys.argv[1] == "revoke":
        print("Revoking credentials...")
        client.revoke_credentials()
        print("Credentials revoked successfully")
        return

    print("Starting OAuth flow...")
    token = client.get_access_token()

    if token:
        print("✅ Authentication successful!")
        print(f"Access token: {token[:20]}...")
    else:
        print("❌ Authentication failed")
        sys.exit(1)


if __name__ == "__main__":
    cli()
