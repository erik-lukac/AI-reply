#!/usr/bin/env python3
"""
respond.py

This script creates a reply for an email using Gmail API authentication.
It takes mandatory arguments:
  --recipient : The email address to reply to.
  --original  : Path to a JSON file (or via STDIN) containing the original email's details.
  
Optional arguments:
  --unread    : If provided, the reply message will be marked as unread.
  --label     : A label value (added as a custom header for demonstration).
  --no-send   : If provided, the email will not be sent but stored as a draft.

The reply subject is constructed as "Re: <original subject>".
The reply body consists of a hard-coded "TEST" message and a reply header that separates
the new response from the original email's HTML content.
"""

import argparse
import json
import sys
import logging
import base64

from email.mime.text import MIMEText
from email.header import decode_header, make_header

# Import Gmail API authentication helper.
from gmail_auth import get_gmail_service

def decode_mime_header(header_value: str) -> str:
    """
    Decode a MIME-encoded header (like a sender or subject) into a Unicode string.
    """
    if header_value:
        try:
            dh = decode_header(header_value)
            return str(make_header(dh))
        except Exception:
            return header_value
    return header_value

def load_original_email(original_arg: str) -> dict:
    """
    Load the original email details from a JSON file or from STDIN.
    Expected JSON keys include: subject, html_text (or email), and optionally sender and time/date.
    """
    try:
        with open(original_arg, "r") as f:
            original_email = json.load(f)
            return original_email
    except FileNotFoundError:
        # If the file is not found, try reading the string from STDIN.
        return json.loads(original_arg)

def build_reply_message(recipient: str, original_email: dict, unread: bool = False, label: str = None) -> MIMEText:
    """
    Build a MIME reply message that mimics Gmail’s native reply format.
    
    - The new subject is "Re: " plus the original subject.
    - The reply body starts with "TEST" as the new message.
    - It then includes a header line and a quoted original message (using blockquote and Gmail-like styles).
    - A custom header "X-Unread" is added if the unread flag is True (for demonstration).
    - A custom header "X-Label" is added if label is provided.
    """
    # Decode headers so that MIME-encoded parts are properly rendered.
    orig_subject = decode_mime_header(original_email.get("subject", "No Subject"))
    orig_sender = decode_mime_header(original_email.get("sender", "Unknown Sender"))
    # Use "time" or "date" as available.
    orig_date = original_email.get("time", original_email.get("date", "Unknown Date"))
    # Use "html_text" if available; otherwise fall back to "email"
    orig_html = original_email.get("html_text", original_email.get("email", ""))
    
    # Ensure the reply subject begins with "Re:" (if not already present)
    if not orig_subject.lower().startswith("re:"):
        reply_subject = "Re: " + orig_subject
    else:
        reply_subject = orig_subject

    # Build the reply header line (similar to Gmail’s "On ... wrote:")
    quoted_header = (
        f"<div style='font-size:12px;color:#777;margin-bottom:5px;'>"
        f"On {orig_date}, {orig_sender} wrote:"
        f"</div>"
    )
    
    # Wrap the original email content in a blockquote to visually separate it.
    quoted_body = (
        "<blockquote style='margin:0 0 0 0.8ex;border-left:1px solid #ccc;padding-left:1ex;'>"
        f"{orig_html}"
        "</blockquote>"
    )
    
    # Combine the new reply with the quoted header and original content.
    reply_body = (
        "<html>"
        "<body>"
        "<div style='font-family:Arial,sans-serif;font-size:14px;'>"
        "<p>TEST</p>"  # Your reply text
        "</div>"
        "<br>"
        f"{quoted_header}{quoted_body}"
        "</body>"
        "</html>"
    )
    
    # Create the MIMEText object with HTML content.
    mime_msg = MIMEText(reply_body, "html")
    mime_msg["To"] = recipient
    mime_msg["Subject"] = reply_subject
    
    # Add a custom header for demonstration.
    if unread:
        mime_msg["X-Unread"] = "yes"
    if label:
        mime_msg["X-Label"] = label

    return mime_msg

def create_draft(service, mime_msg: MIMEText) -> dict:
    """
    Create a draft email using the Gmail API.
    """
    raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    body = {"message": {"raw": raw_message}}
    draft = service.users().drafts().create(userId="me", body=body).execute()
    return draft

def mark_message_unread(service, message_id: str) -> None:
    """
    Modify the message labels to mark the message as unread.
    """
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": ["UNREAD"]}
    ).execute()

def send_message(service, mime_msg: MIMEText) -> dict:
    """
    Send the email using the Gmail API.
    """
    raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    message = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    return message

def main():
    parser = argparse.ArgumentParser(
        description="Create a reply email using Gmail API. "
                    "Mandatory: --recipient and --original (JSON file with the original email details)."
    )
    parser.add_argument("--recipient", type=str, required=True, help="Email address of the recipient.")
    parser.add_argument("--original", type=str, required=True,
                        help="Path to a JSON file (or JSON string) containing the original email details.")
    # Use store_true so that simply providing --unread sets the flag to True.
    parser.add_argument("--unread", action="store_true",
                        help="If provided, mark the reply as unread. (Default is read)")
    parser.add_argument("--label", type=str, help="Optional: Label to add (custom header).")
    parser.add_argument("--no-send", action="store_true",
                        help="If provided, the email will not be sent, only stored as a draft.")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Load the original email details.
    try:
        original_email = load_original_email(args.original)
    except Exception as e:
        logging.error(f"Error loading original email: {e}")
        sys.exit(1)

    # Build the MIME reply message.
    mime_msg = build_reply_message(args.recipient, original_email, unread=args.unread, label=args.label)

    # Authenticate with Gmail.
    service = get_gmail_service()

    try:
        if args.no_send:
            result = create_draft(service, mime_msg)
            logging.info("Draft created successfully.")
            # If the unread flag is set, try marking the draft's underlying message as unread.
            if args.unread:
                message_id = result["message"]["id"]
                mark_message_unread(service, message_id)
                logging.info("Draft marked as unread.")
        else:
            result = send_message(service, mime_msg)
            logging.info("Message sent successfully.")
            # If the unread flag is set, mark the sent message as unread.
            if args.unread:
                message_id = result["id"]
                mark_message_unread(service, message_id)
                logging.info("Message marked as unread.")
    except Exception as e:
        logging.error(f"Error sending/creating draft: {e}")
        sys.exit(1)

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()