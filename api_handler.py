import threading
import queue
import logging
import time
import requests

class ApiHandler:
    def __init__(self, config, retry_settings):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.name = config['name']
        self.method = config.get('method', 'POST').upper()
        self.endpoint = config['endpoint']
        self.headers_template = config.get('headers', {})
        self.payload_template = config.get('payload', {})
        self.timeout = config.get('timeout', 10)
        self.api_queue = queue.Queue()
        self.max_retries = retry_settings.get('max_retries', 3)
        self.initial_delay = retry_settings.get('initial_delay', 10)

    def start(self):
        self.logger.debug(f"Starting API handler for {self.name}")
        thread = threading.Thread(
            target=self.process_api_queue,
            daemon=True,
            name=f"API-{self.name}"
        )
        thread.start()
        return True

    def process_api_queue(self):
        self.logger.debug(f"Starting API processor for {self.name}")
        while True:
            message = self.api_queue.get()
            self.logger.debug(f"Processing API request on {self.name}: {message}, queue size: {self.api_queue.qsize()}")
            retry_count = message.get('retry_count', 0)

            if not self.send_api_request(message, retry_count):
                self.retry_message(message, retry_count)
            self.api_queue.task_done()

    def send_api_request(self, message, retry_count):
        try:
            sender = message.get('sender', '')
            timestamp = message.get('timestamp', '')
            text = message.get('text', '')

            endpoint = self.endpoint.format(sender=sender, timestamp=timestamp, message=text)
            headers = {
                k: v.format(sender=sender, timestamp=timestamp, message=text) if isinstance(v, str) else v
                for k, v in self.headers_template.items()
            }
            if 'User-Agent' not in headers:
                headers['User-Agent'] = f"SMS-Gateway/{self.name}"
            payload = {
                k: v.format(sender=sender, timestamp=timestamp, message=text) if isinstance(v, str) else v
                for k, v in self.payload_template.items()
            }

            self.logger.debug(f"Sending {self.method} request to {endpoint} with headers: {headers}, payload: {payload}")

            if self.method == "POST":
                response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            elif self.method == "GET":
                response = requests.get(endpoint, headers=headers, params=payload if payload else None, timeout=self.timeout)
            elif self.method == "PUT":
                response = requests.put(endpoint, headers=headers, json=payload, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported method: {self.method}")

            response.raise_for_status()
            self.logger.info(f"Sent API request from {self.name} to {endpoint}: {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            error_msg = f"Error sending API request from {self.name}: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f", Status: {e.response.status_code}, Response: {e.response.text}"
            self.logger.error(error_msg)
            return False

    def retry_message(self, message, retry_count):
        if retry_count < self.max_retries:
            delay = self.initial_delay * (2 ** retry_count)
            self.logger.info(f"Retrying API request to {self.name} (attempt {retry_count + 1}/{self.max_retries}) after {delay}s")
            message['retry_count'] = retry_count + 1
            time.sleep(delay)
            self.api_queue.put(message)
        else:
            self.logger.error(f"Max retries ({self.max_retries}) reached for API request to {self.name}")

    def send_api(self, sender, timestamp, text):
        self.api_queue.put({
            'sender': sender,
            'timestamp': timestamp,
            'text': text,
            'retry_count': 0
        })

    def close(self):
        self.logger.debug(f"Closed API handler {self.name}")