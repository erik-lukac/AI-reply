#!/usr/bin/env python3
"""
gmail_auth.py

Handles authentication for both:
  1. Gmail API (using OAuth 2.0 user credentials).
  2. Google Cloud services (using a service account JSON).

Running this module directly (e.g., `python gmail_auth.py`) will demonstrate
the Gmail OAuth flow by building and verifying a Gmail service.

It does NOT automatically demonstrate service account usage. You can import
`get_service_account_credentials` in your scripts that need Pub/Sub or other
GCP APIs authenticated via service accounts.
"""

import os
import pickle
import logging
import argparse
from typing import Any, List

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# For service account credentials:
from google.oauth2 import service_account

# For Gmail API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# =============================================================================
# CONSTANTS SECTION
# =============================================================================

#: The scopes your application needs to access the Gmail API (User OAuth).
SCOPES: List[str] = ["https://www.googleapis.com/auth/gmail.modify"]

#: Default path to the user OAuth credentials.json (located in parent directory).
DEFAULT_CREDENTIALS_PATH: str = os.path.join(
    os.path.dirname(__file__), "..", "credentials.json"
)

#: Default path for storing user OAuth tokens after successful authentication.
DEFAULT_TOKEN_FILE: str = "token.pickle"

#: Default path to the service account JSON file (for Pub/Sub or other GCP services).
DEFAULT_SERVICE_ACCOUNT_PATH: str = os.path.join(
    os.path.dirname(__file__), "..", "service_account.json"
)


# =============================================================================
# USER OAUTH FUNCTIONS (Gmail)
# =============================================================================

def get_credentials(
    credentials_file: str = DEFAULT_CREDENTIALS_PATH,
    token_file: str = DEFAULT_TOKEN_FILE
) -> Credentials:
    """
    Obtain valid user credentials from storage or through an OAuth 2.0 flow
    for Gmail API access.

    Args:
        credentials_file (str): Path to the client secrets file (credentials.json).
        token_file (str): Path to the token file where credentials are (or will be) stored.

    Returns:
        Credentials: Valid OAuth 2.0 credentials for the Gmail API.
    """
    creds: Credentials | None = None

    # Load existing credentials if the token file is present.
    if os.path.exists(token_file):
        with open(token_file, "rb") as token:
            creds = pickle.load(token)
            logging.info(f"Loaded existing user OAuth credentials from '{token_file}'.")

    # If no valid credentials, prompt the user through the OAuth flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired user OAuth credentials.")
            creds.refresh(Request())
        else:
            logging.info(f"Initiating OAuth flow using '{credentials_file}'.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=8080)
        # Save the credentials for next time.
        with open(token_file, "wb") as token:
            pickle.dump(creds, token)
            logging.info(f"Saved new user OAuth credentials to '{token_file}'.")

    return creds


def get_gmail_service(
    credentials_file: str = DEFAULT_CREDENTIALS_PATH,
    token_file: str = DEFAULT_TOKEN_FILE
) -> Any:
    """
    Build and return a Gmail API service object using user OAuth credentials.

    Args:
        credentials_file (str): Path to the client secrets file (credentials.json).
        token_file (str): Path to store/load the user OAuth token pickle.

    Returns:
        Any: An instance of the Gmail API service (googleapiclient.discovery.Resource).
    """
    creds = get_credentials(credentials_file, token_file)
    try:
        service = build("gmail", "v1", credentials=creds)
        logging.info("Gmail service built successfully (user OAuth).")
        return service
    except HttpError as error:
        logging.error(f"Failed to build Gmail service: {error}")
        raise error


# =============================================================================
# SERVICE ACCOUNT FUNCTIONS (Pub/Sub or other GCP services)
# =============================================================================

def get_service_account_credentials(
    service_account_path: str = DEFAULT_SERVICE_ACCOUNT_PATH,
    scopes: List[str] | None = None
) -> service_account.Credentials:
    """
    Load a service account JSON file for Google Cloud authentication.

    Args:
        service_account_path (str): Path to the service account JSON.
        scopes (List[str] | None): Additional scopes to apply. Defaults to None.

    Returns:
        service_account.Credentials: A credentials object for service accounts.
    """
    if not os.path.exists(service_account_path):
        raise FileNotFoundError(
            f"Service account file not found at '{service_account_path}'"
        )

    try:
        creds = service_account.Credentials.from_service_account_file(
            service_account_path, scopes=scopes
        )
        logging.info(f"Loaded service account credentials from '{service_account_path}'.")
        return creds
    except Exception as e:
        logging.error(f"Failed to load service account credentials: {e}")
        raise e


# =============================================================================
# MAIN (for testing user OAuth only)
# =============================================================================

def main() -> None:
    """
    Demonstrates how to initiate or refresh Gmail API credentials directly from this module.
    This doesn't demonstrate service-account usage, but you could add a demo if desired.
    """
    parser = argparse.ArgumentParser(
        description="Authenticate and store Gmail API credentials (user OAuth)."
    )
    parser.add_argument(
        "--credentials-file",
        type=str,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to the user OAuth credentials.json file (default: {DEFAULT_CREDENTIALS_PATH})"
    )
    parser.add_argument(
        "--token-file",
        type=str,
        default=DEFAULT_TOKEN_FILE,
        help=f"Path to store/load the user OAuth token pickle (default: {DEFAULT_TOKEN_FILE})"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Attempt to retrieve or refresh credentials for Gmail
    service = get_gmail_service(
        credentials_file=args.credentials_file,
        token_file=args.token_file
    )

    # Verify authentication by making a simple API call (e.g., getProfile).
    try:
        profile = service.users().getProfile(userId="me").execute()
        logging.info(f"Successfully authenticated. Email: {profile.get('emailAddress')}")
        print(f"\nAuthenticated as: {profile.get('emailAddress')}\n")
    except HttpError as e:
        logging.error(f"Error calling Gmail API: {e}")
        print("Failed to call the Gmail API.")


if __name__ == "__main__":
    main()