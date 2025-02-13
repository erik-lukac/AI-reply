#!/usr/bin/env python3
"""
main.py

Main entrypoint that:
1. Subscribes to Gmail watch notifications (Pub/Sub),
2. On notification, reads new emails in 'autoreply',
3. Creates a draft reply for each new message.
"""

import json
import logging

# Import the functions we need.
from folder_subscribe import subscribe_to_gmail_updates
from read import fetch_unread_messages
from reply import create_draft_reply

logging.basicConfig(level=logging.INFO)

def process_pubsub_message(message):
    """
    Pub/Sub callback for inbound Gmail watch notifications.
    1. Parse the JSON notification (which includes 'emailAddress', 'historyId', etc.).
    2. Fetch unread emails from label 'autoreply'.
    3. Create a draft reply for each new message.
    """
    # Acknowledge the Pub/Sub message to remove it from the queue
    message.ack()

    # Decode and log the message
    data_str = message.data.decode("utf-8")
    logging.info(f"Received Pub/Sub message: {data_str}")

    try:
        notification_data = json.loads(data_str)
        logging.info(f"Notification details: {notification_data}")

        # Step 1: Fetch new/unread emails from label 'autoreply'.
        new_msgs = fetch_unread_messages(label="autoreply")
        if not new_msgs:
            logging.info("No new messages found in 'autoreply' label.")
            return

        # Step 2: For each message, create a draft reply.
        for msg in new_msgs:
            headers = msg.get('payload', {}).get('headers', [])
            msg_id = msg.get('id')

            # Extract 'From' and 'Subject' from message headers
            from_header = next((h["value"] for h in headers if h["name"] == "From"), "")
            subject_header = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")

            # Compose your draft reply content
            reply_subject = f"Re: {subject_header}"
            reply_body = ("Thank you for your email.\n\n"
                          "This is an automated draft reply from our system.\n"
                          "Someone will get back to you shortly.")

            logging.info(f"Creating draft reply to {from_header} for msg_id={msg_id}")
            create_draft_reply(
                to_email=from_header,
                subject=reply_subject,
                body_text=reply_body
            )

            # Optionally, mark the original message as READ to avoid re-processing
            # (If you do this, you won’t keep creating drafts for the same message)
            #
            # from gmail_auth import build_gmail_service
            # service = build_gmail_service()
            # service.users().messages().modify(
            #     userId='me',
            #     id=msg_id,
            #     body={'removeLabelIds': ['UNREAD']}
            # ).execute()

    except Exception as e:
        logging.exception("Error processing Pub/Sub message.")


def main():
    """
    Main entry point: 
    1. Subscribes to Gmail updates via folder_subscribe.py
    2. Ties the callback to `process_pubsub_message`.
    """
    logging.info("Starting main script. Subscribing to Gmail watch notifications...")

    # This function is assumed to continuously listen to Pub/Sub subscription
    # and invoke 'process_pubsub_message' whenever a new message arrives.
    subscribe_to_gmail_updates(process_pubsub_message)


if __name__ == "__main__":
    main()