import threading
import queue
import logging
import time
from gsmmodem.modem import GsmModem
from gsmmodem.exceptions import TimeoutException

class ModemHandler:
    def __init__(self, config, sms_callback, retry_settings):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.name = config.get('name', 'UnnamedModem')
        self.port = config['port']
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        self.modem = None
        self.sms_callback = sms_callback
        self.max_retries = retry_settings.get('max_retries', 3)
        self.initial_delay = retry_settings.get('initial_delay', 10)
        self.network_retries = config.get('network_retries', 3)

    def start(self):
        self.logger.debug(f"Starting modem {self.name}")
        self.modem = GsmModem(
            self.config['port'],
            self.config['baudrate'],
            smsReceivedCallbackFunc=self.handle_sms
        )
        self.modem.smsTextMode = False
        try:
            self.modem.connect(self.config['pin'])
            self.logger.info(f"Connected to modem {self.name}")
        except Exception as e:
            self.logger.error(f"Failed to connect to modem {self.name}: {e}")
            return False

        self.start_threads()
        return True

    def handle_sms(self, sms):
        self.logger.debug(f"Received SMS on {self.name}")
        self.incoming_queue.put(sms)

    def start_threads(self):
        incoming_thread = threading.Thread(
            target=self.process_incoming,
            args=(),
            daemon=True,
            name=f"Incoming-{self.name}"
        )
        incoming_thread.start()

        outgoing_thread = threading.Thread(
            target=self.process_outgoing,
            args=(),
            daemon=True,
            name=f"Outgoing-{self.name}"
        )
        outgoing_thread.start()

    def process_incoming(self):
        self.logger.debug(f"Starting incoming processor for {self.name}")
        while True:
            sms = self.incoming_queue.get()
            self.logger.debug(f"Processing incoming SMS on {self.name}: {sms.text}, queue size: {self.incoming_queue.qsize()}")
            self.sms_callback(self.name, sms)
            self.incoming_queue.task_done()

    def process_outgoing(self):
        self.logger.debug(f"Starting outgoing processor for {self.name}")
        while True:
            message = self.outgoing_queue.get()
            self.logger.debug(f"Processing outgoing message on {self.name}: {message}, queue size: {self.outgoing_queue.qsize()}")
            retry_count = message.get('retry_count', 0)
            
            success = False
            for attempt in range(self.network_retries):
                try:
                    if self.modem.waitForNetworkCoverage(timeout=30):
                        self.modem.sendSms(message['destination'], message['text'])
                        self.logger.info(f"Sent SMS from {self.name} to {message['destination']}: {message['text']}")
                        success = True
                        break
                    else:
                        self.logger.warning(f"No network coverage on {self.name}, attempt {attempt + 1}/{self.network_retries}")
                        time.sleep(5)
                except Exception as e:
                    self.logger.error(f"Error sending SMS from {self.name}: {e}")
                    break
            if not success:
                self.retry_message(message, retry_count)
            self.outgoing_queue.task_done()

    def retry_message(self, message, retry_count):
        if retry_count < self.max_retries:
            delay = self.initial_delay * (2 ** retry_count)
            self.logger.info(f"Retrying message to {message['destination']} (attempt {retry_count + 1}/{self.max_retries}) after {delay}s")
            message['retry_count'] = retry_count + 1
            time.sleep(delay)
            self.outgoing_queue.put(message)
        else:
            self.logger.error(f"Max retries ({self.max_retries}) reached for message to {message['destination']}")

    def send_sms(self, destination, text):
        self.outgoing_queue.put({'destination': destination, 'text': text, 'retry_count': 0})

    def close(self):
        if self.modem:
            self.modem.close()
            self.logger.debug(f"Closed modem connection {self.name}")