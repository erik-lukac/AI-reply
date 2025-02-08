import os
import pickle
import argparse
import logging
from typing import List, Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import read

# Set up logging to the console.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Use the modify scope as required.
SCOPES: List[str] = ['https://www.googleapis.com/auth/gmail.modify']

def get_credentials() -> Credentials:
    """
    Obtain valid user credentials from storage or via an OAuth 2.0 flow.

    Returns:
        Credentials: The obtained OAuth 2.0 credentials.
    """
    creds: Optional[Credentials] = None
    token_file: str = 'token.pickle'

    # Try to load existing credentials.
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
            logging.info("Loaded credentials from token.pickle.")

    # If no valid credentials, initiate the OAuth flow.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing expired credentials.")
            creds.refresh(Request())
        else:
            logging.info("No valid credentials found; initiating OAuth flow.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        # Save the new credentials for future runs.
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
            logging.info("Saved new credentials to token.pickle.")
    return creds

def main() -> None:
    """
    Authenticate with Gmail and dispatch to the appropriate module based on input arguments.
    """
    creds = get_credentials()
    try:
        service = build('gmail', 'v1', credentials=creds)
        logging.info("Gmail service built successfully.")
    except HttpError as error:
        logging.error(f"Failed to build Gmail service: {error}")
        return

    # Set up argument parsing with a subcommand for the read module.
    parser = argparse.ArgumentParser(description="Gmail API Main Application")
    subparsers = parser.add_subparsers(dest='module', required=True, help='Module to run')
    
    # Subcommand: read
    read_parser = subparsers.add_parser('read', help='Read emails with filters')
    read_parser.add_argument('--label', type=str, help='Label to filter emails')
    read_parser.add_argument('--unread', type=str, choices=['yes', 'no'], help='Filter unread emails: "yes" for unread, "no" for read')
    read_parser.add_argument('--subject', type=str, help='Text to filter the email subject')
    read_parser.add_argument('--sender', type=str, help='Sender email address to filter')
    
    args = parser.parse_args()

    if args.module == 'read':
        # Call the read module passing in the Gmail service and the parsed arguments.
        output_json: str = read.run(service, args)
        print(output_json)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()