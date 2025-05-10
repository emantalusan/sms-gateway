import logging
import threading
import time
from collections import deque

class MemoryStore:
    def __init__(self, retention_days):
        self.logger = logging.getLogger(__name__)
        self.sms_store = deque()  # List of (modem_name, number, timestamp, text) tuples
        self.store_lock = threading.Lock()
        self.retention_seconds = retention_days * 86400  # Convert days to seconds
        self.start_cleanup_thread()
        self.logger.debug(f"Initialized in-memory SMS store with retention {retention_days} days")

    def start_cleanup_thread(self):
        """Start a thread to clean up old SMS messages"""
        def cleanup_task():
            while True:
                self.cleanup_old_messages()
                time.sleep(86400)  # Check daily
        thread = threading.Thread(target=cleanup_task, daemon=True, name="SMS-Cleanup")
        thread.start()
        self.logger.debug("Started SMS cleanup thread")

    def cleanup_old_messages(self):
        """Remove SMS messages older than retention period"""
        current_time = time.time()
        with self.store_lock:
            initial_count = len(self.sms_store)
            # Keep messages newer than retention period
            self.sms_store = deque(
                msg for msg in self.sms_store
                if current_time - msg[2] <= self.retention_seconds
            )
            removed_count = initial_count - len(self.sms_store)
            if removed_count > 0:
                self.logger.info(f"Cleaned up {removed_count} old SMS messages")
            else:
                self.logger.debug("No old SMS messages to clean up")

    def save_sms(self, modem_name, sms):
        """Save an SMS to the in-memory store"""
        with self.store_lock:
            self.sms_store.append((modem_name, sms.number, time.time(), sms.text))
        self.logger.info(f"Saved SMS from {sms.number} to memory store from {modem_name}")

    def get_all_sms(self):
        """Retrieve all SMS messages (for debugging or export)"""
        with self.store_lock:
            return list(self.sms_store)