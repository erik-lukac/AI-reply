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
  python read.py --label INBOX --unread yes
  python read.py --subject "Meeting" --sender "boss@example.com"
"""

import argparse
import sys
import json
import logging
from typing import Dict, Any, List
import base64
import email

from gmail_auth import get_gmail_service


def build_query(args: argparse.Namespace) -> str:
    """
    Build a Gmail search query from the provided command-line arguments.
    """
    query_parts = []
    if args.label:
        # Gmail supports searching by label with "label:" operator.
        query_parts.append(f"label:{args.label}")
    if args.unread:
        # "is:unread" or "is:read" operators.
        if args.unread.lower() == "yes":
            query_parts.append("is:unread")
        elif args.unread.lower() == "no":
            query_parts.append("is:read")
    if args.subject:
        # Enclose subject text in quotes to handle spaces.
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
            # We skip attachments.
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
    
    # Fallback if no HTML found.
    if not html_body:
        html_body = "No HTML content found."
    
    return html_body


def get_message_details(service, message_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed information for a given message ID.
    This version fetches the raw email content (full MIME source), decodes it,
    and extracts the HTML body along with sender, subject, time, labels, and unread status.
    """
    # Request the raw message from Gmail.
    message = service.users().messages().get(userId='me', id=message_id, format='raw').execute()
    
    # Get the raw email content and decode it.
    raw_data = message.get('raw')
    try:
        raw_email = base64.urlsafe_b64decode(raw_data.encode('ASCII')).decode('utf-8', errors='replace')
    except Exception as e:
        raw_email = f"Error decoding raw email: {e}"
    
    # Parse the raw email to extract headers and body parts.
    parsed_email = email.message_from_string(raw_email)
    sender = parsed_email.get('From', '')
    subject = parsed_email.get('Subject', '')
    time = parsed_email.get('Date', '')
    
    # Extract the HTML body.
    html_body = extract_html_from_email(parsed_email)
    
    # Get label IDs (e.g., "INBOX", "UNREAD", etc.) from the message metadata.
    labels = message.get('labelIds', [])
    unread = 'UNREAD' in labels  # True if the UNREAD label is present.
    
    # Format the labels as a comma-separated string.
    label_str = ", ".join(labels) if labels else ""
    
    return {
        "sender": sender,
        "subject": subject,
        "time": time,
        "label": label_str,
        "unread": unread,
        # Now returns the HTML body of the email.
        "email": html_body,
    }


def list_filtered_emails(service, query: str) -> List[Dict[str, Any]]:
    """
    List emails matching the provided Gmail query.
    Retrieves detailed information for each email.
    """
    emails = []
    # Initial call to list messages. Note: results may be paginated.
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
        
        # Check if there is a next page.
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
    parser.add_argument('--label', type=str, help='Label to filter emails (e.g., INBOX, STARRED)')
    parser.add_argument('--unread', type=str, choices=['yes', 'no'], help='Filter unread emails: "yes" for unread, "no" for read')
    parser.add_argument('--subject', type=str, help='Text to filter the email subject')
    parser.add_argument('--sender', type=str, help='Sender email address to filter')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Build the query based on the provided arguments.
    query = build_query(args)
    logging.info(f"Using query: {query}")

    # Authenticate and build the Gmail API service.
    service = get_gmail_service()

    # Retrieve emails matching the query.
    emails = list_filtered_emails(service, query)
    logging.info(f"Found {len(emails)} emails matching the criteria.")

    # Output the emails as formatted JSON.
    print(json.dumps(emails, indent=2))


if __name__ == '__main__':
    main()