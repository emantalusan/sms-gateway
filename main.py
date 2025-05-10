import logging
import threading
from modem import ModemHandler
from email_handler import EmailHandler
from api_handler import ApiHandler
from sms_processor import SMSProcessor
from memory_store import MemoryStore
from config import ConfigManager

class SmsGateway:
    def __init__(self, config_file='config.json'):
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        log_level = getattr(logging, self.config_manager.config.get('log_level', 'INFO').upper(), logging.INFO)
        logging.basicConfig(level=log_level)
        self.logger.info(f"Logging level set to {logging.getLevelName(log_level)}")
        self.memory_store = MemoryStore(retention_days=self.config_manager.get_sms_retention_days())
        self.processor = SMSProcessor(
            self.memory_store,
            self.config_manager.get_rules(),
            multipart_timeout_minutes=self.config_manager.get_multipart_timeout_minutes()
        )
        self.modem_handlers = {}
        self.email_handlers = {}
        self.api_handlers = {}

    def start(self):
        self.logger.debug("Starting SMS Gateway")
        
        for modem_conf in self.config_manager.get_modem_configs():
            handler = ModemHandler(modem_conf, self.processor.process_sms, self.config_manager.get_retry_settings())
            self.modem_handlers[modem_conf['name']] = handler
            self.processor.register_modem(modem_conf['port'], handler)
            if handler.start():
                self.logger.debug(f"Started thread for modem {modem_conf['name']}")
        
        for email_conf in self.config_manager.get_email_configs():
            handler = EmailHandler(email_conf, self.config_manager.get_retry_settings())
            self.email_handlers[email_conf['name']] = handler
            self.processor.register_email(email_conf['name'], handler)
            if handler.start():
                self.logger.debug(f"Started thread for email {email_conf['name']}")
        
        for api_conf in self.config_manager.config.get('api_providers', []):
            handler = ApiHandler(api_conf, self.config_manager.get_retry_settings())
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