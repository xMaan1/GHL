#!/usr/bin/env python3
"""
Credentials management utilities
Handles loading and validation of API credentials
"""

import sys
import os
from typing import Dict

def load_zoom_credentials(filename: str = None) -> Dict[str, str]:
    """
    Load Zoom credentials from file
    
    Args:
        filename: Path to credentials file
        
    Returns:
        Dictionary with credentials
    """
    if filename is None:
        filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "client_credentials.txt")
    
    credentials = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        required_keys = ['account-id', 'client-id', 'client-secret']
        for key in required_keys:
            if key not in credentials:
                raise ValueError(f"Missing required credential: {key}")
        
        return credentials
        
    except FileNotFoundError:
        print(f"❌ Credentials file '{filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        sys.exit(1)

def load_ghl_credentials(filename: str = None) -> Dict[str, str]:
    """
    Load GHL credentials from file
    
    Args:
        filename: Path to credentials file
        
    Returns:
        Dictionary with credentials
    """
    if filename is None:
        filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "client_credentials.txt")
    
    credentials = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    credentials[key.strip()] = value.strip()
        
        required_keys = ['ghl-api-key']
        for key in required_keys:
            if key not in credentials:
                raise ValueError(f"Missing required credential: {key}")
        
        return credentials
        
    except FileNotFoundError:
        print(f"❌ Credentials file '{filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading credentials: {e}")
        sys.exit(1)

def load_app_config(filename: str = None) -> Dict[str, str]:
    """
    Load application configuration from file
    
    Args:
        filename: Path to config file
        
    Returns:
        Dictionary with configuration
    """
    if filename is None:
        filename = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config", "app_config.txt")
    
    config = {}
    
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
        
        return config
        
    except FileNotFoundError:
        print(f"⚠️ Config file '{filename}' not found, using defaults")
        return {'ec2-domain': 'https://your-ec2-domain.com'}
    except Exception as e:
        print(f"⚠️ Error loading config: {e}, using defaults")
        return {'ec2-domain': 'https://your-ec2-domain.com'}