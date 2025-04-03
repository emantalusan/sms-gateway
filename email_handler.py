import threading
import queue
import logging
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailHandler:
    def __init__(self, config, retry_settings):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.name = config['name']
        self.server = config['server']
        self.port = config['port']
        self.user = config['user']
        self.password = config['password']
        self.sender = config['sender']
        self.email_queue = queue.Queue()
        self.smtp = None
        self.max_retries = retry_settings.get('max_retries', 3)
        self.initial_delay = retry_settings.get('initial_delay', 10)
        self.keep_alive = config.get('keep_alive', True)

    def start(self):
        self.logger.debug(f"Starting email handler for {self.name}")
        thread = threading.Thread(
            target=self.process_email_queue,
            daemon=True,
            name=f"Email-{self.name}"
        )
        thread.start()
        return True

    def connect(self):
        try:
            self.smtp = smtplib.SMTP(self.server, self.port)
            self.smtp.starttls()
            self.smtp.login(self.user, self.password)
            self.logger.debug(f"Connected to email server {self.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to email server {self.name}: {e}")
            self.smtp = None
            return False

    def disconnect(self):
        if self.smtp:
            try:
                self.smtp.quit()
                self.logger.debug(f"Disconnected from email server {self.name}")
            except Exception as e:
                self.logger.warning(f"Error disconnecting from {self.name}: {e}")
            finally:
                self.smtp = None

    def process_email_queue(self):
        self.logger.debug(f"Starting email processor for {self.name}")
        while True:
            message = self.email_queue.get()
            self.logger.debug(f"Processing email on {self.name}: {message}, queue size: {self.email_queue.qsize()}")
            retry_count = message.get('retry_count', 0)

            if not self.send_email_with_retry(message, retry_count):
                self.retry_message(message, retry_count)
            if not self.keep_alive:
                self.disconnect()
            self.email_queue.task_done()

    def send_email_with_retry(self, message, retry_count):
        if not self.smtp and not self.connect():
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = message['destination']
            msg['Subject'] = "SMS Gateway Notification"
            msg.attach(MIMEText(message['text'], 'plain'))
            
            self.smtp.send_message(msg)
            self.logger.info(f"Sent email from {self.name} to {message['destination']}")
            return True
        except Exception as e:
            self.logger.error(f"Error sending email from {self.name}: {e}")
            self.disconnect()
            return False

    def retry_message(self, message, retry_count):
        if retry_count < self.max_retries:
            delay = self.initial_delay * (2 ** retry_count)
            self.logger.info(f"Retrying email to {message['destination']} (attempt {retry_count + 1}/{self.max_retries}) after {delay}s")
            message['retry_count'] = retry_count + 1
            time.sleep(delay)
            self.email_queue.put(message)
        else:
            self.logger.error(f"Max retries ({self.max_retries}) reached for email to {message['destination']}")

    def send_email(self, destination, text):
        self.email_queue.put({'destination': destination, 'text': text, 'retry_count': 0})

    def close(self):
        if self.smtp:
            self.smtp.quit()
            self.logger.debug(f"Closed email connection {self.name}")
            self.smtp = None