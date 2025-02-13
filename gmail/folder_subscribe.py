#!/usr/bin/env python3
"""
folder_subscribe.py

This script sets up a Gmail watch on a specified Gmail label (folder) and listens
for push notifications via Google Cloud Pub/Sub. It uses:
  - OAuth user credentials (credentials.json + token.pickle) for Gmail API access.
  - A service account JSON for Pub/Sub subscriber authentication.

When a push notification is received, the script will:
  1. Extract the `historyId` from the notification.
  2. Query the Gmail history to find newly added messages.
  3. Display the new message IDs (and optionally fetch full message details).

Usage example:
  python folder_subscribe.py --label autoreply
"""

import os
import sys
import logging
import json
import argparse

# Unified credential imports from gmail_auth.py
from gmail_auth import (
    get_gmail_service,
    get_service_account_credentials,
    DEFAULT_CREDENTIALS_PATH,
    DEFAULT_SERVICE_ACCOUNT_PATH
)

# Google Cloud Pub/Sub
from google.cloud import pubsub_v1

# =============================================================================
# CONSTANTS SECTION
# =============================================================================

#: Default Gmail label to watch
DEFAULT_LABEL: str = "autoreply"

#: Your GCP project details
PROJECT_ID: str = "thematic-center-449912-b0"
PUBSUB_TOPIC: str = f"projects/{PROJECT_ID}/topics/autoreply"
PUBSUB_SUBSCRIPTION: str = f"projects/{PROJECT_ID}/subscriptions/autoreply-sub"

#: We'll store the Gmail service globally once initialized
gmail_service = None

# =============================================================================
# FUNCTIONS
# =============================================================================

def get_label_id(service, label_name: str) -> str | None:
    """
    Retrieve the Gmail label ID for the specified label name.
    """
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])
        for label in labels:
            if label.get("name", "").lower() == label_name.lower():
                return label.get("id")
    except Exception as e:
        logging.error(f"Error retrieving label '{label_name}': {e}")
    return None


def setup_gmail_watch(service, label_id: str, pubsub_topic: str) -> dict:
    """
    Set up a Gmail watch on a given label with push notifications sent to Pub/Sub.
    """
    body = {
        "labelIds": [label_id],
        "topicName": pubsub_topic
    }
    try:
        response = service.users().watch(userId="me", body=body).execute()
        logging.info(f"Gmail watch set up successfully: {response}")
        return response
    except Exception as e:
        logging.error(f"Failed to set up Gmail watch: {e}")
        sys.exit(1)


def process_history(service, start_history_id: str) -> None:
    """
    Use the Gmail API to fetch history events since start_history_id,
    extract new message IDs, and log them.
    """
    try:
        history_response = service.users().history().list(
            userId="me", startHistoryId=start_history_id
        ).execute()

        if "history" in history_response:
            for history_item in history_response["history"]:
                if "messagesAdded" in history_item:
                    for msg in history_item["messagesAdded"]:
                        msg_id = msg["message"]["id"]
                        logging.info(f"New message added with id: {msg_id}")
        else:
            logging.info("No new history items found.")
    except Exception as e:
        logging.error(f"Error processing history since {start_history_id}: {e}")


def pubsub_callback(message) -> None:
    """
    Callback function to process Pub/Sub messages.
    Extracts the historyId from the notification and triggers history processing.
    """
    try:
        message_data: str = message.data.decode("utf-8")
        logging.info(f"Received Pub/Sub message: {message_data}")

        notification = json.loads(message_data)
        logging.info(f"Notification details: {notification}")

        history_id = notification.get("historyId")
        if history_id:
            process_history(gmail_service, history_id)
        else:
            logging.warning("No historyId found in the notification.")
    except Exception as e:
        logging.error(f"Error in Pub/Sub callback: {e}")
    finally:
        message.ack()


def listen_for_pubsub_messages(subscription: str, service_account_file: str) -> None:
    """
    Listen on the specified Pub/Sub subscription for incoming messages,
    using a service account for authentication.
    """
    # Load the service account credentials (Pub/Sub)
    try:
        creds = get_service_account_credentials(service_account_path=service_account_file)
    except FileNotFoundError as fnfe:
        logging.error(fnfe)
        sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to load service account credentials: {e}")
        sys.exit(1)

    subscriber = pubsub_v1.SubscriberClient(credentials=creds)
    streaming_pull_future = subscriber.subscribe(subscription, callback=pubsub_callback)
    logging.info(f"Listening for messages on subscription: {subscription} ...")

    try:
        streaming_pull_future.result()  # This blocks indefinitely
    except Exception as e:
        logging.error(f"Error while listening for Pub/Sub messages: {e}")
        streaming_pull_future.cancel()


# =============================================================================
# MAIN
# =============================================================================

def main():
    global gmail_service

    parser = argparse.ArgumentParser(
        description="Set up a Gmail watch on a specified label and listen for push notifications via Pub/Sub."
    )
    parser.add_argument(
        "--label",
        type=str,
        default=DEFAULT_LABEL,
        help="Gmail label to watch (default: autoreply)"
    )
    parser.add_argument(
        "--credentials",
        type=str,
        default=DEFAULT_CREDENTIALS_PATH,
        help=f"Path to the user OAuth credentials.json (default: {DEFAULT_CREDENTIALS_PATH})"
    )
    parser.add_argument(
        "--service-account",
        type=str,
        default=DEFAULT_SERVICE_ACCOUNT_PATH,
        help=f"Path to the service account JSON (default: {DEFAULT_SERVICE_ACCOUNT_PATH})"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # If you want to replicate the original "cd" approach
    os.chdir(os.path.dirname(args.credentials))
    logging.info(f"Changed working directory to {os.getcwd()} to locate user OAuth credentials.")

    # 1. Authenticate with Gmail using user OAuth
    gmail_service = get_gmail_service(credentials_file=args.credentials)

    # 2. Retrieve the label ID
    label_id = get_label_id(gmail_service, args.label)
    if not label_id:
        logging.error(f"Label '{args.label}' not found in your Gmail account.")
        sys.exit(1)
    logging.info(f"Found label '{args.label}' with ID: {label_id}")

    # 3. Set up Gmail push notifications for that label
    setup_gmail_watch(gmail_service, label_id, PUBSUB_TOPIC)

    # 4. Listen for incoming Pub/Sub notifications, using the service account
    listen_for_pubsub_messages(PUBSUB_SUBSCRIPTION, args.service_account)


if __name__ == "__main__":
    main()