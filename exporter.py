import argparse
import base64
import json
import os
from datetime import datetime
from io import BytesIO
from typing import Dict, List

import requests
from PIL import Image as PILImage
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle

class SlackExporter:
    """
    Utility class to export messages from a Slack channel.

    Attributes:
        token (str): The Slack API token used for authentication.
        headers (dict): The HTTP headers used for Slack API requests.
        users_cache (dict): A cache to store user information.
    """

    def __init__(self, token: str):
        """
        Initializes the SlackExporter with the provided Slack API token.

        Args:
            token (str): The Slack API token.
        """
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
        self.users_cache = {}

    def get_channel_id(self, channel_name: str) -> str:
        """
        Retrieves the channel ID for the given channel name.

        Args:
            channel_name (str): The name of the Slack channel.

        Returns:
            str: The channel ID.
        """
        response = requests.get(
            "https://slack.com/api/conversations.list",
            headers=self.headers,
            params={"types": "public_channel,private_channel"}
        )
        channels = response.json()["channels"]
        channel = next((c for c in channels if c["name"] == channel_name), None)
        if channel:
            return channel["id"]
        else:
            return ""

    def fetch_user_info(self, user_id: str) -> Dict:
        """
        Retrieves user information for the given user ID.

        Args:
            user_id (str): The Slack user ID.

        Returns:
            dict: The user information, including the user's name, real name, and profile image (if available).
        """
        if user_id in self.users_cache:
            return self.users_cache[user_id]

        response = requests.get(
            f"https://slack.com/api/users.info",
            headers=self.headers,
            params={"user": user_id}
        )
        result = response.json()
        if not result["ok"]:
            return {"name": user_id, "image": ""}

        user = result["user"]
        image_url = user["profile"].get("image_48", "")
        image_data = ""
        if image_url:
            img_response = requests.get(image_url, headers=self.headers)
            if img_response.status_code == 200:
                image_data = base64.b64encode(img_response.content).decode('utf-8')

        user_info = {
            "id": user_id,
            "name": user["profile"].get("display_name") or user["name"],
            "real_name": user["profile"].get("real_name", ""),
            "image": image_data
        }
        self.users_cache[user_id] = user_info
        return user_info

    def download_image(self, url: str) -> str:
        """
        Downloads an image from the given URL and returns it as a base64-encoded string.

        Args:
            url (str): The URL of the image to be downloaded.

        Returns:
            str: The base64-encoded image data.
        """
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode('utf-8')
        return ""

    def process_message(self, message: Dict) -> Dict:
        """
        Processes a Slack message and returns a dictionary with the relevant information.

        Args:
            message (dict): The Slack message data.

        Returns:
            dict: The processed message data, including the user information, message text, timestamp, and any attached images.
        """
        user_info = self.fetch_user_info(message.get("user", ""))
        processed = {
            "user": user_info,
            "text": message.get("text", ""),
            "timestamp": message.get("ts", ""),
            "thread_ts": message.get("thread_ts", ""),
            "files": []
        }

        if "files" in message:
            for file in message["files"]:
                if file["mimetype"].startswith("image/"):
                    image_data = self.download_image(file["url_private"])
                    if image_data:
                        processed["files"].append({
                            "name": file["name"],
                            "mimetype": file["mimetype"],
                            "data": image_data
                        })

        return processed

    def fetch_thread_replies(self, channel_id: str, thread_ts: str) -> List[Dict]:
        """
        Fetches the replies for a Slack message thread.

        Args:
            channel_id (str): The ID of the Slack channel.
            thread_ts (str): The timestamp of the parent message in the thread.

        Returns:
            list: A list of dictionaries, where each dictionary represents a reply message.
        """
        replies = []
        cursor = None

        while True:
            params = {
                "channel": channel_id,
                "ts": thread_ts,
                "limit": 100
            }
            if cursor:
                params["cursor"] = cursor

            response = requests.get(
                "https://slack.com/api/conversations.replies",
                headers=self.headers,
                params=params
            )

            result = response.json()
            if not result["ok"]:
                print(f"Failed to fetch replies: {result['error']}")
                break

            thread_messages = result["messages"][1:]  # Skip parent message
            replies.extend([self.process_message(m) for m in thread_messages])

            if not result.get("has_more", False):
                break
            cursor = result["response_metadata"]["next_cursor"]

        # Sort replies by timestamp
        replies.sort(key=lambda x: float(x['timestamp']))
        return replies

    def export_channel(self, channel_name: str) -> List[Dict]:
        """
        Exports the messages from the specified Slack channel.

        Args:
            channel_name (str): The name of the Slack channel.

        Returns:
            list: A list of dictionaries, where each dictionary represents a message.
        """
        channel_id = self.get_channel_id(channel_name)
        if not channel_id:
            return []

        requests.post(
            "https://slack.com/api/conversations.join",
            headers=self.headers,
            json={"channel": channel_id}
        )

        all_messages = []
        cursor = None
        oldest_first = True  # Set to True to get oldest messages first

        while True:
            params = {
                "channel": channel_id,
                "limit": 100,
                "oldest": "0" if oldest_first else None,  # Start from oldest messages
            }
            if cursor:
                params["cursor"] = cursor

            response = requests.get(
                "https://slack.com/api/conversations.history",
                headers=self.headers,
                params=params
            )

            result = response.json()
            if not result["ok"]:
                raise Exception(f"Failed to fetch messages: {result['error']}")

            messages = result["messages"]
            if oldest_first:
                messages.reverse()  # Reverse to maintain oldest-to-newest order

            for msg in messages:
                processed_msg = self.process_message(msg)
                if msg.get("reply_count", 0) > 0:
                    replies = self.fetch_thread_replies(channel_id, msg["ts"])
                    processed_msg["replies"] = replies
                else:
                    processed_msg["replies"] = []
                all_messages.append(processed_msg)

            if not result.get("has_more", False):
                break
            cursor = result["response_metadata"]["next_cursor"]

        if not oldest_first:
            all_messages.reverse()  # Reverse if we fetched newest-first

        return all_messages


class SlackPDFExporter:
    """
    Utility class to export Slack messages to a PDF document.

    Attributes:
        exporter (SlackExporter): An instance of the SlackExporter class.
        styles (dict): The styles used for the PDF document.
    """

    def __init__(self, token: str):
        """
        Initializes the SlackPDFExporter with the provided Slack API token.

        Args:
            token (str): The Slack API token.
        """
        self.exporter = SlackExporter(token)
        self.styles = getSampleStyleSheet()
        self.setup_styles()

    def setup_styles(self):
        """
        Sets up the styles used for the PDF document.
        """
        self.styles.add(ParagraphStyle(
            name='ThreadMessage',
            parent=self.styles['Normal'],
            leftIndent=50,
            spaceBefore=5,
            spaceAfter=5
        ))

    def create_message_table(self, message, is_thread=False):
        """
        Creates a table representation of a Slack message.

        Args:
            message (dict): The processed Slack message data.
            is_thread (bool, optional): Indicates whether the message is a reply in a thread.

        Returns:
            Table: A ReportLab Table object representing the Slack message.
        """
        avatar_data = None
        if message['user']['image']:
            img_data = base64.b64decode(message['user']['image'])
            img = PILImage.open(BytesIO(img_data))
            img = img.resize((24, 24))
            avatar_io = BytesIO()
            img.save(avatar_io, format='PNG')
            avatar_data = Image(BytesIO(avatar_io.getvalue()), width=24, height=24)

        timestamp = datetime.fromtimestamp(float(message['timestamp']))
        formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        style = self.styles['ThreadMessage'] if is_thread else self.styles['Normal']
        content = [[
            avatar_data or '',
            Paragraph(f"<b>{message['user']['name']}</b> {formatted_time}", style),
        ]]

        content.append(['', Paragraph(message['text'], style)])

        if message['files']:
            for file in message['files']:
                if file['data']:
                    img_data = base64.b64decode(file['data'])
                    img = PILImage.open(BytesIO(img_data))
                    w, h = img.size
                    aspect = w / h
                    max_width = 400
                    width = min(w, max_width)
                    height = width / aspect
                    img_obj = Image(BytesIO(img_data), width=width, height=height)
                    content.append(['', img_obj])

        table = Table(content, colWidths=[0.4 * inch, 6 * inch])
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        return table

    def export_to_pdf(self, channel_name: str, output_file: str):
        """
        Exports the messages from the specified Slack channel to a PDF document.

        Args:
            channel_name (str): The name of the Slack channel.
            output_file (str): The path to the output PDF file.
        """
        messages = self.exporter.export_channel(channel_name)

        doc = SimpleDocTemplate(
            output_file,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []
        title = Paragraph(f"Slack Export - #{channel_name}", self.styles['Heading1'])
        story.append(title)
        story.append(Spacer(1, 12))

        for message in messages:
            story.append(self.create_message_table(message))
            if message.get('replies'):
                for reply in message['replies']:
                    story.append(self.create_message_table(reply, is_thread=True))
            story.append(Spacer(1, 12))
        doc.build(story)


def main():
    """
    The main function that handles the command-line interface.
    """
    parser = argparse.ArgumentParser(description='Export Slack channel messages')
    parser.add_argument('--format', choices=['json', 'pdf'], default='json', help='Output format')
    args = parser.parse_args()

    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise ValueError("SLACK_TOKEN environment variable not set")

    channel_name = "helene-logging"

    if args.format == 'json':
        exporter = SlackExporter(token)
        messages = exporter.export_channel(channel_name)
        output = {
            "channel": channel_name,
            "exported_at": datetime.now().isoformat(),
            "messages": messages
        }
        with open("slack_export.json", "w") as f:
            json.dump(output, f, indent=2)
    else:
        exporter = SlackPDFExporter(token)
        exporter.export_to_pdf(channel_name, "slack_export.pdf")


if __name__ == "__main__":
    main()