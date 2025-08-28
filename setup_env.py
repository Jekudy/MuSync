#!/usr/bin/env python3
"""
Setup environment variables from user_tokens.json
"""

import json
import os
import sys

def setup_environment():
    """Setup environment variables from user_tokens.json"""
    try:
        with open('user_tokens.json', 'r') as f:
            tokens = json.load(f)
        
        # Get the first user (assuming single user for now)
        user_key = list(tokens.keys())[0]
        user_tokens = tokens[user_key]
        
        # Set Yandex token
        if 'yandex' in user_tokens:
            os.environ['YANDEX_ACCESS_TOKEN'] = user_tokens['yandex']['token']
            print("✓ Yandex token set")
        
        # Set Spotify tokens
        if 'spotify_access' in user_tokens:
            os.environ['SPOTIFY_ACCESS_TOKEN'] = user_tokens['spotify_access']['token']
            print("✓ Spotify access token set")
        
        if 'spotify_refresh' in user_tokens:
            os.environ['SPOTIFY_REFRESH_TOKEN'] = user_tokens['spotify_refresh']['token']
            print("✓ Spotify refresh token set")
        
        print("Environment variables set successfully!")
        return True
        
    except Exception as e:
        print(f"Error setting up environment: {e}")
        return False

if __name__ == '__main__':
    setup_environment()

