#!/usr/bin/env python3
"""Convert tokens from current format to expected format."""

import json
import os

def convert_tokens():
    """Convert tokens from current format to expected format."""
    
    # Read current tokens
    with open('user_tokens.json', 'r') as f:
        current_data = json.load(f)
    
    # Extract tokens from current format
    jekudy = current_data.get('jekudy', {})
    
    # Create new format
    new_data = {
        'yandex': {
            'access_token': jekudy.get('yandex', {}).get('token', '')
        },
        'spotify': {
            'access_token': jekudy.get('spotify_access', {}).get('token', ''),
            'refresh_token': jekudy.get('spotify_refresh', {}).get('token', ''),
            'client_id': jekudy.get('spotify_client', {}).get('token', ''),
            'client_secret': jekudy.get('spotify_secret', {}).get('token', '')
        }
    }
    
    # Write new format
    with open('user_tokens.json', 'w') as f:
        json.dump(new_data, f, indent=2)
    
    print("Tokens converted successfully!")
    print(f"Yandex access token: {'✓' if new_data['yandex']['access_token'] else '✗'}")
    print(f"Spotify access token: {'✓' if new_data['spotify']['access_token'] else '✗'}")
    print(f"Spotify refresh token: {'✓' if new_data['spotify']['refresh_token'] else '✗'}")
    print(f"Spotify client ID: {'✓' if new_data['spotify']['client_id'] else '✗'}")
    print(f"Spotify client secret: {'✓' if new_data['spotify']['client_secret'] else '✗'}")

if __name__ == '__main__':
    convert_tokens()

