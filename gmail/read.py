#!/usr/bin/env python3
"""
read.py

This script reads emails from your Gmail account using filters provided via command-line
arguments. It outputs a JSON list where each email object has the following fields:
  - id          (the Gmail message id)
  - sender
  - subject
  - time
  - label
  - unread
  - email       (the HTML body of the email)

Usage example:
  python read.py --label INBOX --unread --subject "Meeting" --sender "boss@example.com"
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import argparse
import sys
import json
import logging
import os
import base64
import email
from typing import Dict, Any, List

# =============================================================================
# IMPORT AUTH
# =============================================================================
from gmail_auth import get_gmail_service, DEFAULT_CREDENTIALS_PATH

# =============================================================================
# CONSTANTS SECTION (Output file only, credentials remain in gmail_auth)
# =============================================================================
DEFAULT_OUTPUT_FILE: str = "emails.json"


# =============================================================================
# FUNCTIONS
# =============================================================================
def build_query(args: argparse.Namespace) -> str:
    """
    Build a Gmail search query from the provided command-line arguments.
    """
    query_parts: List[str] = []
    if args.label:
        query_parts.append(f"label:{args.label}")
    if args.unread:
        query_parts.append("is:unread")
    if args.subject:
        query_parts.append(f'subject:"{args.subject}"')
    if args.sender:
        query_parts.append(f"from:{args.sender}")
    return " ".join(query_parts)


def extract_html_from_email(parsed_email: email.message.Message) -> str:
    """
    Extract the HTML body from a parsed email message.
    If the email is multipart, it walks through the parts and returns the first HTML part found.
    If the email is not multipart and its content type is text/html, it returns that.
    """
    html_body: str | None = None

    if parsed_email.is_multipart():
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
        # Not multipart. If the content type is HTML, extract directly.
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


def get_message_details(service: Any, message_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed information for a given message ID.
    Decodes the raw email content and extracts relevant information.
    """
    message = service.users().messages().get(userId="me", id=message_id, format="raw").execute()
    raw_data: str | None = message.get("raw")

    try:
        raw_email = (
            base64.urlsafe_b64decode(raw_data.encode("ASCII")).decode("utf-8", errors="replace")
            if raw_data
            else ""
        )
    except Exception as e:
        raw_email = f"Error decoding raw email: {e}"

    parsed_email = email.message_from_string(raw_email)
    sender: str = parsed_email.get("From", "")
    subject: str = parsed_email.get("Subject", "")
    time: str = parsed_email.get("Date", "")

    html_body: str = extract_html_from_email(parsed_email)

    labels: List[str] = message.get("labelIds", [])
    unread: bool = ("UNREAD" in labels)
    label_str: str = ", ".join(labels) if labels else ""

    return {
        "id": message_id,
        "sender": sender,
        "subject": subject,
        "time": time,
        "label": label_str,
        "unread": unread,
        "email": html_body,
    }


def list_filtered_emails(service: Any, query: str) -> List[Dict[str, Any]]:
    """
    List emails matching the provided Gmail query.
    Retrieves detailed information for each email.
    """
    emails: List[Dict[str, Any]] = []
    response = service.users().messages().list(userId="me", q=query).execute()
    messages = response.get("messages", [])

    while messages:
        for msg in messages:
            message_id: str = msg.get("id", "")
            try:
                details = get_message_details(service, message_id)
                emails.append(details)
            except Exception as e:
                logging.error(f"Failed to retrieve details for message ID {message_id}: {e}")

        page_token = response.get("nextPageToken")
        if page_token:
            response = service.users().messages().list(userId="me", q=query, pageToken=page_token).execute()
            messages = response.get("messages", [])
        else:
            break

    return emails


def main() -> None:
    """
    Main entry point for reading and filtering emails via Gmail API.
    """
    parser = argparse.ArgumentParser(
        description="Read emails with filters. Use the options below to define your search criteria.",
        epilog="""
Examples:
  python read.py --label INBOX --unread --subject "Meeting" --sender "boss@example.com"
  python read.py --label PROMOTIONS --sender "newsletter@example.org"
"""
    )

    # Allow the user to override the credentials path, but the default now comes from gmail_auth.py
    parser.add_argument(
        "--credentials",
        type=str,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to credentials.json (default: {DEFAULT_CREDENTIALS_PATH})"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file for saving emails (default: {DEFAULT_OUTPUT_FILE})"
    )

    # Email filter arguments
    parser.add_argument("--label", type=str, help="Label to filter emails (e.g., INBOX, STARRED)")
    parser.add_argument("--unread", action="store_true", help="Filter unread emails")
    parser.add_argument("--subject", type=str, help="Text to filter the email subject")
    parser.add_argument("--sender", type=str, help="Sender email address to filter")

    # Show help if no arguments are provided.
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # If you still want to replicate the original behavior of changing directory:
    os.chdir(os.path.dirname(args.credentials))
    logging.info(f"Changed working directory to {os.getcwd()} to locate credentials.json.")

    # Build the Gmail query from user filters
    query: str = build_query(args)
    logging.info(f"Using query: {query}")

    # Initialize the Gmail service with the specified credentials file
    service: Any = get_gmail_service(credentials_file=args.credentials)

    # Retrieve matching emails
    emails: List[Dict[str, Any]] = list_filtered_emails(service, query)
    logging.info(f"Found {len(emails)} emails matching the criteria.")

    # Print emails to the console
    print(json.dumps(emails, indent=2, ensure_ascii=False))

    # Save emails to the output file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        logging.info(f"Emails successfully saved to '{args.output}'")
    except Exception as e:
        logging.error(f"Failed to save emails to file: {e}")


if __name__ == "__main__":
    main()