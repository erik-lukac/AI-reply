#!/usr/bin/env python3
"""
main.py

Main entrypoint that:
  1. Subscribes to Gmail watch notifications (via Pub/Sub).
  2. On notification, reads new emails in the 'autoreply' label.
  3. Creates a draft reply for each new message.

Usage:
    python main.py

Examples:
    # Simply run the script to start listening for notifications.
    $ python main.py
"""

import json
import logging
from typing import Any, Dict, List

# Import the Pub/Sub Message type for type annotations.
from google.cloud.pubsub_v1.subscriber.message import Message

# Import our modular functions.
from folder_subscribe import subscribe_to_gmail_updates
from read import fetch_unread_messages
from reply import create_draft_reply

# -----------------------------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def extract_email_headers(headers: List[Dict[str, Any]]) -> (str, str):
    """
    Extract the 'From' and 'Subject' values from a list of header dictionaries.

    Args:
        headers: List of header dictionaries.

    Returns:
        A tuple (from_header, subject_header).
    """
    from_header: str = next(
        (h["value"] for h in headers if h.get("name", "").lower() == "from"),
        ""
    )
    subject_header: str = next(
        (h["value"] for h in headers if h.get("name", "").lower() == "subject"),
        "No Subject"
    )
    return from_header, subject_header

# -----------------------------------------------------------------------------
# Core Email Processing Functions
# -----------------------------------------------------------------------------
def process_new_emails(label: str = "autoreply") -> None:
    """
    Fetch unread messages from the specified label and create a draft reply for each.

    Args:
        label: The Gmail label to check for unread messages (default "autoreply").
    """
    new_msgs: List[Dict[str, Any]] = fetch_unread_messages(label=label)
    if not new_msgs:
        logging.info(f"No new messages found in '{label}' label.")
        return

    for msg in new_msgs:
        headers: List[Dict[str, Any]] = msg.get("payload", {}).get("headers", [])
        msg_id: str = msg.get("id", "unknown")
        from_header, subject_header = extract_email_headers(headers)

        reply_subject: str = f"Re: {subject_header}"
        reply_body: str = (
            "Thank you for your email.\n\n"
            "This is an automated draft reply from our system.\n"
            "Someone will get back to you shortly."
        )

        logging.info(f"Creating draft reply to {from_header} for msg_id={msg_id}")
        create_draft_reply(
            to_email=from_header,
            subject=reply_subject,
            body_text=reply_body
        )
        # Optional: Mark the original message as read to avoid re-processing.
        # This can be added here if a function to mark messages as read is available.

# -----------------------------------------------------------------------------
# Pub/Sub Callback
# -----------------------------------------------------------------------------
def process_pubsub_message(message: Message) -> None:
    """
    Callback for inbound Pub/Sub messages.

    This function:
      1. Acknowledges the Pub/Sub message.
      2. Logs and parses the notification.
      3. Triggers processing of new unread emails.

    Args:
        message: The Pub/Sub Message instance.
    """
    # Acknowledge the Pub/Sub message.
    message.ack()

    data_str: str = message.data.decode("utf-8")
    logging.info(f"Received Pub/Sub message: {data_str}")

    try:
        notification_data: Dict[str, Any] = json.loads(data_str)
        logging.info(f"Notification details: {notification_data}")

        # Process unread emails from the specified label.
        process_new_emails(label="autoreply")

    except Exception as e:
        logging.exception(f"Error processing Pub/Sub message: {e}")

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
def main() -> None:
    """
    Main entry point.

    Subscribes to Gmail watch notifications via Pub/Sub. The provided callback
    handles new messages by fetching unread emails and creating draft replies.

    Example:
        $ python main.py
    """
    logging.info("Starting main script. Subscribing to Gmail watch notifications...")
    subscribe_to_gmail_updates(callback=process_pubsub_message)

# -----------------------------------------------------------------------------
# Script Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    main()