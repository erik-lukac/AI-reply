#!/usr/bin/env python3
"""
reply.py

This module creates a reply for an email using Gmail API authentication.
It reads email details from a JSON file and sends a reply via the Gmail API.

This module can be imported and its functions used programmatically.
When executed as a script, it parses CLI arguments and performs the reply action.

Usage examples:
    # Reply to the first email in emails.json:
    python reply.py --recipient "user@example.com"
    
    # Reply with CC recipients:
    python reply.py --recipient "user@example.com" --cc '["john@doe.com", "yep@yap.cz"]'
    
    # Reply with HTML response:
    python reply.py --recipient "user@example.com" --response "<div>Thank you</div>"
    
    # Save as draft:
    python reply.py --recipient "user@example.com" --draft
    
    # Reply with default signature (from signature.html):
    python reply.py --recipient "user@example.com" --response "Thank you" --signature
    
    # Reply with custom signature file:
    python reply.py --recipient "user@example.com" --response "Thank you" --signature "path/to/custom_signature.html"
    
Mandatory arguments:
  --recipient : The email address to reply to

Optional arguments:
  --credentials : Path to credentials.json (default: see gmail_auth.py)
  --original    : Path to JSON file with email details (default: see below)
  --response    : Custom response text/HTML to use in reply
  --cc          : JSON array of CC recipients
  --signature   : Use signature from file (default: see below)
  --label       : Add a label to the email
  --draft       : Store as unread draft instead of sending
"""

import argparse
import json
import sys
import logging
import os
import base64
from email.mime.text import MIMEText
from email.header import decode_header, make_header
from typing import Any, List, Dict, Optional

# =============================================================================
# IMPORT AUTH
# =============================================================================
from gmail_auth import get_gmail_service, DEFAULT_CREDENTIALS_PATH

# =============================================================================
# MODULE PUBLIC API
# =============================================================================
__all__ = [
    "decode_mime_header",
    "load_original_emails",
    "load_signature",
    "build_reply_message",
    "create_draft",
    "mark_message_unread",
    "send_message",
    "main",
]

# =============================================================================
# CONSTANTS SECTION
# =============================================================================
DEFAULT_EMAIL_DETAILS_FILE: str = "emails.json"
DEFAULT_SIGNATURE_FILE: str = "signature.html"


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


def load_original_emails(original_arg: str) -> List[Dict[str, Any]]:
    """
    Load all email details from a JSON file or from STDIN.
    Returns a list of emails.
    """
    try:
        if original_arg == "-":
            email_data = json.load(sys.stdin)
        else:
            with open(original_arg, "r") as f:
                email_data = json.load(f)
        
        if isinstance(email_data, dict):
            return [email_data]
        if isinstance(email_data, list):
            if not email_data:
                raise ValueError("No emails found in JSON file.")
            return email_data
        raise ValueError("Invalid JSON format.")
    except Exception as e:
        logging.error(f"Error loading email data: {e}")
        sys.exit(1)


def load_signature(signature_path: str = DEFAULT_SIGNATURE_FILE) -> str:
    """
    Load HTML signature from file.
    """
    try:
        with open(signature_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.warning(f"Signature file '{signature_path}' not found.")
        return ""
    except Exception as e:
        logging.error(f"Error loading signature: {e}")
        return ""


def build_reply_message(
    recipient: str,
    original_email: Dict[str, Any],
    response: Optional[str] = None,
    cc_list: Optional[List[str]] = None,
    label: Optional[str] = None,
    signature: Optional[str] = None
) -> MIMEText:
    """
    Build a MIME reply message that mimics Gmail’s native reply format.
    """
    # Decode headers
    orig_subject: str = decode_mime_header(original_email.get("subject", "No Subject"))
    orig_sender: str = decode_mime_header(original_email.get("sender", "Unknown Sender"))
    orig_date: str = original_email.get("time", original_email.get("date", "Unknown Date"))
    # Use "html_text" if available; otherwise, fallback to the "email" field.
    orig_html: str = original_email.get("html_text", original_email.get("email", ""))

    # Ensure the reply subject begins with "Re:" (if not already present).
    reply_subject = orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"

    # Quoted header line.
    quoted_header = (
        f"<div style='font-size:12px;color:#777;margin-bottom:5px;'>"
        f"On {orig_date}, {orig_sender} wrote:"
        f"</div>"
    )

    # Wrap the original email content in a blockquote.
    quoted_body = (
        "<blockquote style='margin:0 0 0 0.8ex;border-left:1px solid #ccc;padding-left:1ex;'>"
        f"{orig_html}"
        "</blockquote>"
    )

    # Combine the reply with the quoted header and original content.
    reply_body = (
        "<html>"
        "<body>"
        "<div style='font-family:Arial,sans-serif;font-size:14px;'>"
        f"<p>{response if response else ''}</p>"
        f"{signature if signature else ''}"
        "</div>"
        "<br>"
        f"{quoted_header}{quoted_body}"
        "</body>"
        "</html>"
    )

    # Create the MIMEText object with HTML content.
    mime_msg = MIMEText(reply_body, "html")
    mime_msg["To"] = recipient

    if cc_list:
        mime_msg["Cc"] = ", ".join(cc_list)

    mime_msg["Subject"] = reply_subject

    # Add a custom header if a label is provided.
    if label:
        mime_msg["X-Label"] = label

    return mime_msg


def create_draft(service: Any, mime_msg: MIMEText) -> Dict[str, Any]:
    """
    Create a draft email using the Gmail API.
    """
    raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    body = {"message": {"raw": raw_message}}
    draft = service.users().drafts().create(userId="me", body=body).execute()
    return draft


def mark_message_unread(service: Any, message_id: str) -> None:
    """
    Modify the message labels to mark the message as unread.
    """
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": ["UNREAD"]}
    ).execute()


def send_message(service: Any, mime_msg: MIMEText) -> Dict[str, Any]:
    """
    Send the email using the Gmail API.
    """
    raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()
    message = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
    return message


def main(args_list: Optional[List[str]] = None) -> None:
    """
    Main entry point for creating and sending (or drafting) a reply email using the Gmail API.
    
    When used as a module, an optional list of arguments can be provided.
    If no arguments are passed, it defaults to sys.argv[1:].
    """
    parser = argparse.ArgumentParser(
        description="Create a reply email using Gmail API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Send reply:
    python reply.py --recipient user@example.com
    
    # Save as draft:
    python reply.py --recipient user@example.com --draft
    
    # Reply with custom response:
    python reply.py --recipient user@example.com --response "Thank you"
        """
    )

    parser.add_argument(
        "--credentials",
        type=str,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to credentials.json (default: {DEFAULT_CREDENTIALS_PATH})"
    )
    parser.add_argument(
        "--original",
        type=str,
        default=DEFAULT_EMAIL_DETAILS_FILE,
        help=f"Path to JSON file with email details (default: {DEFAULT_EMAIL_DETAILS_FILE})"
    )
    parser.add_argument(
        "--signature",
        nargs="?",
        const=DEFAULT_SIGNATURE_FILE,
        help=f"Use signature from file (default: {DEFAULT_SIGNATURE_FILE})"
    )

    parser.add_argument("--recipient", type=str, required=True, help="Email address of the recipient")
    parser.add_argument("--response", type=str, help="Custom response text/HTML to use in reply")
    parser.add_argument("--cc", type=str, help='JSON array of CC recipients (e.g. \'["john@doe.com"]\')')
    parser.add_argument("--label", type=str, help="Label to add to the email")
    parser.add_argument("--draft", action="store_true", help="Store as unread draft instead of sending")

    if args_list is None:
        args_list = sys.argv[1:]
    if not args_list:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args(args_list)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Change directory to locate credentials.json (if needed)
    os.chdir(os.path.dirname(args.credentials))
    logging.info(f"Changed working directory to {os.getcwd()} to locate credentials.json.")

    # Process the CC list if provided.
    cc_list: Optional[List[str]] = None
    if args.cc:
        try:
            parsed_cc = json.loads(args.cc)
            if not isinstance(parsed_cc, list):
                raise ValueError("CC argument must be a JSON array of email addresses.")
            cc_list = parsed_cc
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON format in CC argument: {e}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error processing CC list: {e}")
            sys.exit(1)

    # Load signature if requested.
    signature_str: Optional[str] = None
    if args.signature:
        signature_str = load_signature(args.signature)

    try:
        # Initialize Gmail service using gmail_auth.
        service = get_gmail_service(credentials_file=args.credentials)
        logging.info("Gmail service initialized successfully.")

        # Load original emails.
        emails = load_original_emails(args.original)
        results: List[Dict[str, Any]] = []

        for idx, email_data in enumerate(emails, start=1):
            logging.info(f"Processing email {idx} of {len(emails)}...")
            mime_msg = build_reply_message(
                recipient=args.recipient,
                original_email=email_data,
                response=args.response,
                cc_list=cc_list,
                label=args.label,
                signature=signature_str
            )

            if args.draft:
                result = create_draft(service, mime_msg)
                message_id: str = result["message"]["id"]
                mark_message_unread(service, message_id)
                logging.info(f"Draft {idx} created and marked as unread.")
            else:
                result = send_message(service, mime_msg)
                logging.info(f"Message {idx} sent successfully.")
            
            results.append(result)

        print(json.dumps(results, indent=2))
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()