#!/usr/bin/env python3
"""
read.py

This script reads emails from your Gmail account using filters provided via command-line
arguments. It outputs a JSON list where each email object has the following fields:
  - sender
  - subject
  - time
  - label
  - unread
  - email  (the HTML body of the email)

Usage examples:
  python read.py --label INBOX --unread --subject "Meeting" --sender "boss@example.com"
"""

# =============================================================================
# CONSTANTS SECTION
# =============================================================================
import os

# Default path to credentials.json (located in the parent directory of this script)
DEFAULT_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
# Default output file for saving the emails
DEFAULT_OUTPUT_FILE = "emails.json"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import argparse
import sys
import json
import logging
from typing import Dict, Any, List
import base64
import email

# Import the Gmail API authentication helper.
from gmail_auth import get_gmail_service


# =============================================================================
# FUNCTIONS
# =============================================================================
def build_query(args: argparse.Namespace) -> str:
    """
    Build a Gmail search query from the provided command-line arguments.
    """
    query_parts = []
    if args.label:
        query_parts.append(f"label:{args.label}")
    if args.unread:
        query_parts.append("is:unread")
    if args.subject:
        query_parts.append(f'subject:"{args.subject}"')
    if args.sender:
        query_parts.append(f'from:{args.sender}')
    return " ".join(query_parts)


def extract_html_from_email(parsed_email: email.message.Message) -> str:
    """
    Extract the HTML body from a parsed email message.
    If the email is multipart, it walks through the parts and returns the first HTML part found.
    If the email is not multipart and its content type is text/html, it returns that.
    """
    html_body = None

    if parsed_email.is_multipart():
        # Walk through the email parts and look for HTML content.
        for part in parsed_email.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            # Skip attachments.
            if content_type == "text/html" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception as e:
                    logging.error(f"Error decoding HTML part: {e}")
                    html_body = f"Error decoding HTML content: {e}"
                    break
    else:
        # Not multipart. If the content type is HTML, extract it.
        if parsed_email.get_content_type() == "text/html":
            try:
                charset = parsed_email.get_content_charset() or "utf-8"
                html_body = parsed_email.get_payload(decode=True).decode(charset, errors="replace")
            except Exception as e:
                logging.error(f"Error decoding HTML content: {e}")
                html_body = f"Error decoding HTML content: {e}"
    
    if not html_body:
        html_body = "No HTML content found."
    
    return html_body


def get_message_details(service, message_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed information for a given message ID.
    Decodes the raw email content and extracts relevant information.
    """
    message = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
    raw_data = message.get('raw')
    try:
        raw_email = base64.urlsafe_b64decode(raw_data.encode('ASCII')).decode('utf-8', errors='replace')
    except Exception as e:
        raw_email = f"Error decoding raw email: {e}"
    
    parsed_email = email.message_from_string(raw_email)
    sender = parsed_email.get('From', '')
    subject = parsed_email.get('Subject', '')
    time = parsed_email.get('Date', '')
    
    html_body = extract_html_from_email(parsed_email)
    labels = message.get('labelIds', [])
    unread = 'UNREAD' in labels
    label_str = ", ".join(labels) if labels else ""
    
    return {
        "sender": sender,
        "subject": subject,
        "time": time,
        "label": label_str,
        "unread": unread,
        "email": html_body,
    }


def list_filtered_emails(service, query: str) -> List[Dict[str, Any]]:
    """
    List emails matching the provided Gmail query.
    Retrieves detailed information for each email.
    """
    emails = []
    response = service.users().messages().list(userId='me', q=query).execute()
    messages = response.get('messages', [])

    while messages:
        for msg in messages:
            message_id = msg.get('id')
            try:
                details = get_message_details(service, message_id)
                emails.append(details)
            except Exception as e:
                logging.error(f"Failed to retrieve details for message ID {message_id}: {e}")
        
        page_token = response.get('nextPageToken')
        if page_token:
            response = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
            messages = response.get('messages', [])
        else:
            break

    return emails


def main():
    parser = argparse.ArgumentParser(
        description="Read emails with filters. Use the options below to define your search criteria."
    )
    
    # Parameterize key file paths.
    parser.add_argument("--credentials", type=str, default=DEFAULT_CREDENTIALS_PATH,
                        help=f"Path to credentials.json (default: {DEFAULT_CREDENTIALS_PATH})")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_FILE,
                        help=f"Output file for saving emails (default: {DEFAULT_OUTPUT_FILE})")
    
    # Email filter arguments.
    parser.add_argument('--label', type=str, help='Label to filter emails (e.g., INBOX, STARRED)')
    parser.add_argument('--unread', action='store_true', help='Filter unread emails')
    parser.add_argument('--subject', type=str, help='Text to filter the email subject')
    parser.add_argument('--sender', type=str, help='Sender email address to filter')

    # Show help if no arguments are provided.
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # =============================================================================
    # CHANGE WORKING DIRECTORY BASED ON CREDENTIALS PATH
    # =============================================================================
    os.chdir(os.path.dirname(args.credentials))
    logging.info(f"Changed working directory to {os.getcwd()} to locate credentials.json.")

    # Build the Gmail query.
    query = build_query(args)
    logging.info(f"Using query: {query}")

    # Initialize the Gmail service.
    service = get_gmail_service()

    # Retrieve matching emails.
    emails = list_filtered_emails(service, query)
    logging.info(f"Found {len(emails)} emails matching the criteria.")

    # Print emails to the console.
    print(json.dumps(emails, indent=2, ensure_ascii=False))
    
    # Save emails to the output file.
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        logging.info(f"Emails successfully saved to {args.output}")
    except Exception as e:
        logging.error(f"Failed to save emails to file: {e}")


if __name__ == '__main__':
    main()