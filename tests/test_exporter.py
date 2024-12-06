import base64
import unittest
from unittest.mock import patch, Mock

from exporter import SlackExporter, SlackPDFExporter


class TestSlackExporter(unittest.TestCase):
    def setUp(self):
        self.token = "test-token"
        self.exporter = SlackExporter(self.token)

    @patch('requests.get')
    def test_get_channel_id(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            "channels": [{"name": "test-channel", "id": "C123456"}]
        }
        mock_get.return_value = mock_response

        channel_id = self.exporter.get_channel_id("test-channel")
        self.assertEqual(channel_id, "C123456")
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_fetch_user_info(self, mock_get):
        user_response = Mock()
        user_response.json.return_value = {
            "ok": True,
            "user": {
                "name": "testuser",
                "profile": {
                    "display_name": "Test User",
                    "real_name": "Test Real Name",
                    "image_48": "http://example.com/image.jpg"
                }
            }
        }

        image_response = Mock()
        image_response.status_code = 200
        image_response.content = b"fake-image-data"

        mock_get.side_effect = [user_response, image_response]
        user_info = self.exporter.fetch_user_info("U123456")

        self.assertEqual(user_info["name"], "Test User")
        self.assertEqual(user_info["real_name"], "Test Real Name")
        self.assertEqual(user_info["image"],
                         base64.b64encode(b"fake-image-data").decode('utf-8'))

    @patch('requests.get')
    def test_fetch_thread_replies(self, mock_get):
        user_response = Mock()
        user_response.json.return_value = {
            "ok": True,
            "user": {
                "name": "testuser",
                "profile": {
                    "display_name": "Test User",
                    "real_name": "Test Real Name",
                    "image_48": ""
                }
            }
        }

        thread_response = Mock()
        thread_response.json.return_value = {
            "ok": True,
            "messages": [
                {"text": "Parent message", "ts": "1234567.89"},
                {"text": "Reply 1", "ts": "1234567.90", "user": "U123456"},
                {"text": "Reply 2", "ts": "1234567.91", "user": "U123456"}
            ],
            "has_more": False
        }

        mock_get.side_effect = [thread_response, user_response, user_response]
        replies = self.exporter.fetch_thread_replies("C123456", "1234567.89")

        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[0]["text"], "Reply 1")
        self.assertEqual(replies[1]["text"], "Reply 2")

    @patch('requests.get')
    def test_process_message(self, mock_get):
        user_response = Mock()
        user_response.json.return_value = {
            "ok": True,
            "user": {
                "name": "testuser",
                "profile": {
                    "display_name": "Test User",
                    "real_name": "Test Real Name",
                    "image_48": ""
                }
            }
        }
        mock_get.return_value = user_response

        message = {
            "user": "U123456",
            "text": "Test message",
            "ts": "1234567.89"
        }

        processed = self.exporter.process_message(message)
        self.assertEqual(processed["text"], "Test message")
        self.assertEqual(processed["timestamp"], "1234567.89")
        self.assertEqual(processed["user"]["name"], "Test User")

    @patch('requests.get')
    def test_fetch_user_info_failed_request(self, mock_get):
        user_response = Mock()
        user_response.json.return_value = {"ok": False, "error": "user_not_found"}
        mock_get.return_value = user_response

        user_info = self.exporter.fetch_user_info("U123456")
        self.assertEqual(user_info["name"], "U123456")

    @patch('requests.get')
    def test_process_message_with_files(self, mock_get):
        user_response = Mock()
        user_response.json.return_value = {
            "ok": True,
            "user": {
                "name": "testuser",
                "profile": {
                    "display_name": "Test User",
                    "real_name": "Test Real Name"
                }
            }
        }

        image_response = Mock()
        image_response.status_code = 200
        image_response.content = b"image_data"

        mock_get.side_effect = [user_response, image_response]

        message = {
            "user": "U123456",
            "text": "Test message",
            "ts": "1234567.89",
            "files": [{
                "name": "test.jpg",
                "mimetype": "image/jpeg",
                "url_private": "http://example.com/test.jpg"
            }]
        }

        processed = self.exporter.process_message(message)
        self.assertEqual(len(processed["files"]), 1)
        self.assertEqual(processed["files"][0]["name"], "test.jpg")


class TestSlackPDFExporter(unittest.TestCase):
    def setUp(self):
        self.token = "test-token"
        self.pdf_exporter = SlackPDFExporter(self.token)

    @patch('PIL.Image.open')
    def test_create_message_table(self, mock_pil_open):
        mock_image = Mock()
        mock_image.size = (48, 48)
        mock_image.save = Mock()
        mock_pil_open.return_value = mock_image

        message = {
            "user": {
                "name": "Test User",
                "image": base64.b64encode(b"fake-image-data").decode('utf-8')
            },
            "text": "Test message",
            "timestamp": "1234567.89",
            "files": []
        }

        table = self.pdf_exporter.create_message_table(message)
        self.assertIsNotNone(table)

    def test_setup_styles(self):
        self.assertIn('ThreadMessage', self.pdf_exporter.styles.byName)
        thread_style = self.pdf_exporter.styles['ThreadMessage']
        self.assertEqual(thread_style.leftIndent, 50)


if __name__ == '__main__':
    unittest.main()
