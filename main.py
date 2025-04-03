import json
import logging
import threading
from modem import ModemHandler
from email_handler import EmailHandler
from api_handler import ApiHandler
from sms_processor import SMSProcessor
from database import DatabaseManager

class SmsGateway:
    def __init__(self, config_file='config.json'):
        self.logger = logging.getLogger(__name__)
        self.load_config(config_file)
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper(), logging.INFO)
        logging.basicConfig(level=log_level)
        self.logger.info(f"Logging level set to {logging.getLevelName(log_level)}")
        self.db_manager = DatabaseManager()
        self.processor = SMSProcessor(self.db_manager, self.rules)
        self.modem_handlers = {}
        self.email_handlers = {}
        self.api_handlers = {}

    def load_config(self, config_file):
        self.logger.debug("Loading configuration")
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        required_modem_fields = ['name', 'port', 'baudrate']
        required_email_fields = ['name', 'server', 'port', 'user', 'password', 'sender']
        required_api_fields = ['name', 'method', 'endpoint']

        self.modem_config = config.get('modems', [])
        for modem in self.modem_config:
            if not all(field in modem for field in required_modem_fields):
                raise ValueError(f"Modem config missing required fields: {required_modem_fields}")

        self.email_config = config.get('email_providers', [])
        for email in self.email_config:
            if not all(field in email for field in required_email_fields):
                raise ValueError(f"Email config missing required fields: {required_email_fields}")

        self.api_config = config.get('api_providers', [])
        for api in self.api_config:
            if not all(field in api for field in required_api_fields):
                raise ValueError(f"API config missing required fields: {required_api_fields}")

        self.rules = config.get('rules', [])
        self.retry_settings = config.get('retry_settings', {})
        self.config = config  # Store full config for log_level access

    def start(self):
        self.logger.debug("Starting SMS Gateway")
        
        for modem_conf in self.modem_config:
            handler = ModemHandler(modem_conf, self.processor.process_sms, self.retry_settings)
            self.modem_handlers[modem_conf['name']] = handler
            self.processor.register_modem(modem_conf['port'], handler)
            if handler.start():
                self.logger.debug(f"Started thread for modem {modem_conf['name']}")
        
        for email_conf in self.email_config:
            handler = EmailHandler(email_conf, self.retry_settings)
            self.email_handlers[email_conf['name']] = handler
            self.processor.register_email(email_conf['name'], handler)
            if handler.start():
                self.logger.debug(f"Started thread for email {email_conf['name']}")
        
        for api_conf in self.api_config:
            handler = ApiHandler(api_conf, self.retry_settings)
            self.api_handlers[api_conf['name']] = handler
            self.processor.register_api(api_conf['name'], handler)
            if handler.start():
                self.logger.debug(f"Started thread for api {api_conf['name']}")

    def run(self):
        self.start()
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            for handler in self.modem_handlers.values():
                handler.close()
            for handler in self.email_handlers.values():
                handler.close()
            for handler in self.api_handlers.values():
                handler.close()
            for handler_dict in [self.modem_handlers, self.email_handlers, self.api_handlers]:
                for handler in handler_dict.values():
                    if hasattr(handler, 'incoming_queue'):
                        handler.incoming_queue.join()
                    if hasattr(handler, 'outgoing_queue'):
                        handler.outgoing_queue.join()
                    if hasattr(handler, 'email_queue'):
                        handler.email_queue.join()
                    if hasattr(handler, 'api_queue'):
                        handler.api_queue.join()
            self.logger.info("All queues processed, shutdown complete.")

if __name__ == "__main__":
    gateway = SmsGateway()
    gateway.run()