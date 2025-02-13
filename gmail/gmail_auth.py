#!/usr/bin/env python3
"""
gmail_auth.py

Handles authentication to the Gmail API using OAuth 2.0 credentials
stored in 'credentials.json' (located in the parent directory of this script)
and a local 'token.pickle'.

Run this module directly (python gmail_auth.py) to initiate or refresh
Gmail API credentials.
"""

import os
import pickle
import logging
import argparse
from typing import Any, List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# =============================================================================
# CONSTANTS SECTION
# =============================================================================

#: The scopes your application needs to access the Gmail API.
SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.modify"]

#: The default path to credentials.json (located in the parent directory).
DEFAULT_CREDENTIALS_PATH: str = os.path.join(os.path.dirname(__file__), "..", "credentials.json")

#: Default path for storing OAuth tokens after successful authentication.
DEFAULT_TOKEN_FILE: str = "token.pickle"


def get_credentials(
    credentials_file: str = DEFAULT_CREDENTIALS_PATH,
    token_file: str = DEFAULT_TOKEN_FILE
) -> Credentials:
    """
    Obtain valid user credentials from storage or through an OAuth 2.0 flow.

    Args:
        credentials_file (str): Path to the client secrets file (credentials.json).
        token_file (str): Path to the token file where credentials are (or will be) stored.

    Returns:
        Credentials: Valid OAuth 2.0 credentials for Gmail API.
    """
    creds: Credentials | None = None

    # Load existing credentials if the token file is present.
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)
            logging.info(f"Loaded existing credentials from '{token_file}'.")

    # If no valid credentials, prompt the user through the OAuth flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired credentials.")
            creds.refresh(Request())
        else:
            logging.info(f"Initiating OAuth flow using '{credentials_file}'.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=8080)
        # Save the credentials for next time.
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)
            logging.info(f"Saved new credentials to '{token_file}'.")

    return creds


def get_gmail_service(
    credentials_file: str = DEFAULT_CREDENTIALS_PATH,
    token_file: str = DEFAULT_TOKEN_FILE
) -> Any:
    """
    Build and return a Gmail API service object.

    Args:
        credentials_file (str): Path to the client secrets file (credentials.json).
        token_file (str): Path to the token file for loading/saving credentials.

    Returns:
        Any: An instance of the Gmail API service (googleapiclient.discovery.Resource).
    """
    creds = get_credentials(credentials_file, token_file)
    try:
        service = build("gmail", "v1", credentials=creds)
        logging.info("Gmail service built successfully.")
        return service
    except HttpError as error:
        logging.error(f"Failed to build Gmail service: {error}")
        raise error


def main() -> None:
    """
    Demonstrates how to initiate or refresh Gmail API credentials directly from this module.
    """
    parser = argparse.ArgumentParser(description="Authenticate and store Gmail API credentials.")
    parser.add_argument(
        "--credentials-file",
        type=str,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to the credentials.json file (default: {DEFAULT_CREDENTIALS_PATH})"
    )
    parser.add_argument(
        "--token-file",
        type=str,
        default=DEFAULT_TOKEN_FILE,
        help=f"Path to store/load the token pickle (default: {DEFAULT_TOKEN_FILE})"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Attempt to retrieve or refresh credentials.
    service = get_gmail_service(args.credentials_file, args.token_file)

    # Verify the authentication by making a simple API call (e.g., getProfile).
    try:
        profile = service.users().getProfile(userId="me").execute()
        logging.info(f"Successfully authenticated. Email: {profile.get('emailAddress')}")
        print(f"\nAuthenticated as: {profile.get('emailAddress')}\n")
    except HttpError as e:
        logging.error(f"Error calling Gmail API: {e}")
        print("Failed to call the Gmail API.")


if __name__ == "__main__":
    main()