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

from gmail_auth import get_gmail_service
from google.cloud import pubsub_v1
from google.oauth2 import service_account

# =============================================================================
# CONSTANTS SECTION
# =============================================================================

# Path to the user OAuth credentials file (for Gmail).
CREDENTIALS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "credentials.json")
)

# Path to your service account JSON file (for Pub/Sub).
SERVICE_ACCOUNT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "service_account.json")
)

# Gmail label to watch (default can be changed via --label).
DEFAULT_LABEL = "autoreply"

# Your GCP project details
PROJECT_ID = "thematic-center-449912-b0"
PUBSUB_TOPIC = f"projects/{PROJECT_ID}/topics/autoreply"
PUBSUB_SUBSCRIPTION = f"projects/{PROJECT_ID}/subscriptions/autoreply-sub"

# Global Gmail service variable (will be set in main)
gmail_service = None

# =============================================================================
# FUNCTIONS
# =============================================================================

def get_label_id(service, label_name: str) -> str:
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
        response = service.users().watch(userId='me', body=body).execute()
        logging.info(f"Gmail watch set up successfully: {response}")
        return response
    except Exception as e:
        logging.error(f"Failed to set up Gmail watch: {e}")
        sys.exit(1)

def process_history(service, start_history_id):
    """
    Use the Gmail API to fetch history events since start_history_id,
    extract new message IDs, and (optionally) fetch the full message details.
    """
    try:
        history_response = service.users().history().list(
            userId="me", startHistoryId=start_history_id
        ).execute()

        if 'history' in history_response:
            for history_item in history_response['history']:
                # Look for events that added messages
                if 'messagesAdded' in history_item:
                    for msg in history_item['messagesAdded']:
                        msg_id = msg['message']['id']
                        logging.info(f"New message added with id: {msg_id}")
                        # Optionally, fetch full message details:
                        # full_msg = service.users().messages().get(userId="me", id=msg_id).execute()
                        # logging.info(f"Full message details: {full_msg}")
        else:
            logging.info("No new history items found.")
    except Exception as e:
        logging.error(f"Error processing history since {start_history_id}: {e}")

def pubsub_callback(message):
    """
    Callback function to process Pub/Sub messages.
    Extracts the historyId from the notification and triggers history processing.
    """
    try:
        message_data = message.data.decode('utf-8')
        logging.info(f"Received Pub/Sub message: {message_data}")

        notification = json.loads(message_data)
        logging.info(f"Notification details: {notification}")

        # Extract historyId from the notification and process it
        history_id = notification.get("historyId")
        if history_id:
            # Process the history from this historyId to get new message ids
            process_history(gmail_service, history_id)
        else:
            logging.warning("No historyId found in the notification.")
    except Exception as e:
        logging.error(f"Error in Pub/Sub callback: {e}")
    finally:
        message.ack()

def listen_for_pubsub_messages(subscription: str):
    """
    Listen on the specified Pub/Sub subscription for incoming messages,
    using a service account for authentication.
    """
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        logging.error(f"Service account file not found: {SERVICE_ACCOUNT_PATH}")
        sys.exit(1)

    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH
        )
    except Exception as e:
        logging.error(f"Failed to load service account credentials: {e}")
        sys.exit(1)

    subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
    streaming_pull_future = subscriber.subscribe(subscription, callback=pubsub_callback)
    logging.info(f"Listening for messages on subscription: {subscription} ...")
    try:
        streaming_pull_future.result()  # This will block indefinitely.
    except Exception as e:
        logging.error(f"Error while listening for Pub/Sub messages: {e}")
        streaming_pull_future.cancel()

# =============================================================================
# MAIN FUNCTION
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
    
    args = parser.parse_args()

    # Change working directory so 'credentials.json' is found
    credentials_dir = os.path.dirname(CREDENTIALS_PATH)
    if not os.path.exists(CREDENTIALS_PATH):
        logging.error(f"Credentials file not found at {CREDENTIALS_PATH}")
        sys.exit(1)

    os.chdir(credentials_dir)
    logging.info(f"Changed working directory to {os.getcwd()} to locate credentials.json.")

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 1. Authenticate with Gmail using user OAuth
    gmail_service = get_gmail_service()

    # 2. Retrieve the label ID for the specified Gmail label
    label_id = get_label_id(gmail_service, args.label)
    if not label_id:
        logging.error(f"Label '{args.label}' not found in your Gmail account.")
        sys.exit(1)
    logging.info(f"Found label '{args.label}' with ID: {label_id}")

    # 3. Set up Gmail push notifications (watch) for the specified label
    setup_gmail_watch(gmail_service, label_id, PUBSUB_TOPIC)

    # 4. Listen for incoming Pub/Sub notifications
    listen_for_pubsub_messages(PUBSUB_SUBSCRIPTION)

if __name__ == '__main__':
    main()