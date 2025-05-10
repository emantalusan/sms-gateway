import json
import os
import logging

CONFIG_FILE = 'config.json'

class ConfigManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self.load_config()

    def load_config(self):
        self.logger.debug("Loading configuration")
        if not os.path.exists(CONFIG_FILE):
            default_config = {
                "log_level": "DEBUG",
                "modems": [{"name": "Modem1", "port": "/dev/ttyUSB0", "baudrate": 115200, "pin": None, "network_retries": 3}],
                "email_providers": [{"name": "DefaultEmail", "server": "smtp.example.com", "port": 587, "user": "user@example.com", "password": "password", "sender": "user@example.com", "keep_alive": True}],
                "api_providers": [],
                "retry_settings": {"max_retries": 3, "initial_delay": 10},
                "rules": [{"name": "test1", "sender": ["+96895021117"]}],
                "sms_retention_days": 7,  # Retention period for SMS messages
                "multipart_timeout_minutes": 5  # Timeout for multipart SMS parts
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)
            self.logger.info(f"Created default config file: {CONFIG_FILE}")
        
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            self.logger.debug(f"Loaded config for modems: {[m.get('name', 'Unnamed') for m in config['modems']]}")
            self.logger.debug(f"Loaded config for email providers: {[e.get('name', 'Unnamed') for e in config.get('email_providers', [])]}")
            self.logger.debug(f"Loaded rules: {[r['name'] for r in config.get('rules', [])]}")
            self.logger.debug(f"Loaded SMS retention: {config.get('sms_retention_days', 2)} days")
            self.logger.debug(f"Loaded multipart timeout: {config.get('multipart_timeout_minutes', 2)} minutes")
            return config

    def get_modem_configs(self):
        return self.config['modems']

    def get_email_configs(self):
        return self.config.get('email_providers', [])

    def get_rules(self):
        return self.config.get('rules', [])

    def get_retry_settings(self):
        return self.config.get('retry_settings', {"max_retries": 3, "initial_delay": 10})

    def get_sms_retention_days(self):
        return self.config.get('sms_retention_days', 7)

    def get_multipart_timeout_minutes(self):
        return self.config.get('multipart_timeout_minutes', 5)