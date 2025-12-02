#!/bin/sh

# Setup script for the BrainLift MCP Server
echo "Setting up BrainLift MCP Server..." >&2

# Install dependencies (if needed)
echo "Installing dependencies..." >&2
uv sync > /dev/null 2>&1

# Build project (if needed)
echo "Building the project..." >&2
uv pip install -e . > /dev/null 2>&1

# Setup OAuth2 configuration if platform variables are available
if [ -n "$API_KEY" ] && [ -n "$API_BASE_URL" ] && [ -n "$HIVE_INSTANCE_ID" ]; then
    echo "Fetching OAuth2 configuration..." >&2
    
    if curl -s -X GET "$API_BASE_URL/api/hive-instances/$HIVE_INSTANCE_ID/oauth2-config" \
        -H "x-api-key: $API_KEY" > oauth_response.json 2>&1; then
        
        # Save credentials in the format expected by our MCP server
        echo "Configuring OAuth2 credentials..." >&2
        
        # Convert to Google OAuth2 authorized user format, including id_token if present
        jq '{
          "client_id": .oauthKeys.client_id,
          "client_secret": .oauthKeys.client_secret,
          "refresh_token": .credentials.refresh_token,
          "token": .credentials.access_token,
          "id_token": .credentials.id_token,
          "type": "authorized_user"
        }' oauth_response.json > ./.gcp-saved-token.json
        
        # Create client secrets in Google OAuth format  
        mkdir -p ./credentials
        jq '{"web": .oauthKeys}' oauth_response.json > credentials/client-secrets.json

        echo "OAuth2 credentials configured successfully" >&2
        echo "Credentials:" >&2
        cat credentials/client-secrets.json >&2
        echo "Tokens:" >&2
        cat .gcp-saved-token.json >&2
        
        rm oauth_response.json
    else
        echo "OAuth2 configuration fetch failed, will use manual setup" >&2
    fi
fi

echo "Setup complete" >&2

# Output final JSON configuration to stdout (MANDATORY)
cat << EOF
{
  "command": "uv",
  "args": ["run", "brainlift-mcp"],
  "env": {
    "OAUTH_CLIENT_SECRET_PATH": "./credentials/client-secrets.json",
    "OAUTH_CLIENT_TOKEN_PATH": "./.gcp-saved-token.json"
  },
  "cwd": "$(pwd)"
}
EOF


