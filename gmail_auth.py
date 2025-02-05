#!/usr/bin/env python3
"""
gmail_auth.py

This module provides a function to authenticate with the Gmail API
and return an authorized service instance. It uses OAuth 2.0 credentials
stored in 'token.pickle' and the client secrets from 'credentials.json'.
"""

import os
import pickle
import logging
from typing import Any

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the required scopes.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_credentials() -> Credentials:
    """
    Obtains valid user credentials from storage or through an OAuth 2.0 flow.

    Returns:
        Credentials: The obtained OAuth 2.0 credentials.
    """
    creds = None
    token_file = 'token.pickle'

    # Check if token.pickle exists.
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
            logging.info("Loaded credentials from token.pickle.")

    # If there are no (valid) credentials available, initiate the OAuth flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired credentials.")
            creds.refresh(Request())
        else:
            logging.info("No valid credentials available; initiating OAuth flow.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        # Save the credentials for the next run.
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
            logging.info("Saved new credentials to token.pickle.")

    return creds

def get_gmail_service() -> Any:
    """
    Authenticates with the Gmail API and returns an authorized service instance.

    Returns:
        service: An instance of the Gmail API service.
    Raises:
        HttpError: If there is an error building the Gmail service.
    """
    creds = get_credentials()
    try:
        service = build('gmail', 'v1', credentials=creds)
        logging.info("Gmail service built successfully.")
        return service
    except HttpError as error:
        logging.error(f"An error occurred while building the Gmail service: {error}")
        raise error

# For testing purposes only: running this module will authenticate and print a success message.
if __name__ == '__main__':
    try:
        service = get_gmail_service()
        print("Successfully authenticated with Gmail API.")
    except Exception as e:
        print(f"Failed to authenticate with Gmail API: {e}")