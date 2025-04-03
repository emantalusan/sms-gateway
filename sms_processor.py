import logging
import sqlite3
from gsmmodem.pdu import Concatenation
import re

class SMSProcessor:
    def __init__(self, db_manager, rules):
        self.logger = logging.getLogger(__name__)
        self.db_manager = db_manager
        self.rules = rules
        self.modem_handlers = {}
        self.email_handlers = {}
        self.api_handlers = {}
        self.init_multipart_db()

    def init_multipart_db(self):
        with sqlite3.connect(self.db_manager.db_file) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS multipart_sms
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender TEXT,
                            ref_number INTEGER,
                            total_parts INTEGER,
                            part_number INTEGER,
                            text TEXT,
                            timestamp TEXT,
                            modem_name TEXT,
                            processed INTEGER DEFAULT 0,
                            UNIQUE(sender, ref_number, modem_name, part_number))''')
        self.logger.debug("Initialized multipart SMS database table")

    def register_modem(self, port, handler):
        self.modem_handlers[handler.name] = handler

    def register_email(self, name, handler):
        self.email_handlers[name] = handler

    def register_api(self, name, handler):
        self.api_handlers[name] = handler

    def process_sms(self, modem_name, sms):
        self.logger.debug(f"Handling SMS from {modem_name}, text: {sms.text}")
        complete_sms = self.handle_multipart(modem_name, sms)
        if complete_sms:
            self.db_manager.save_sms(modem_name, complete_sms)
            self.apply_rules(modem_name, complete_sms)

    def handle_multipart(self, modem_name, sms):
        sender = sms.number
        timestamp = sms.time.isoformat()

        if hasattr(sms, 'udh') and sms.udh:
            self.logger.debug(f"SMS has UDH: {sms.udh}")
            for udh_element in sms.udh:
                if isinstance(udh_element, Concatenation):
                    ref_num = udh_element.reference
                    total_parts = udh_element.parts
                    part_num = udh_element.number
                    
                    self.logger.debug(f"Multipart SMS on {modem_name} - Ref: {ref_num}, Part: {part_num}/{total_parts}")
                    
                    with sqlite3.connect(self.db_manager.db_file) as conn:
                        try:
                            conn.execute('''INSERT INTO multipart_sms 
                                          (sender, ref_number, total_parts, part_number, text, timestamp, modem_name)
                                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                       (sender, ref_num, total_parts, part_num, sms.text, timestamp, modem_name))
                        except sqlite3.IntegrityError:
                            self.logger.warning(f"Duplicate multipart SMS part detected: {sender}, ref {ref_num}, part {part_num}")
                            return None

                        cursor = conn.execute('''SELECT COUNT(*) 
                                               FROM multipart_sms 
                                               WHERE ref_number = ? AND sender = ? AND modem_name = ?''',
                                            (ref_num, sender, modem_name))
                        received_parts = cursor.fetchone()[0]
                        
                        if received_parts == total_parts:
                            self.logger.debug(f"All parts received for ref {ref_num} from {sender} on {modem_name}")
                            cursor = conn.execute('''SELECT text 
                                                   FROM multipart_sms 
                                                   WHERE ref_number = ? AND sender = ? AND modem_name = ?
                                                   ORDER BY part_number''',
                                                (ref_num, sender, modem_name))
                            parts = cursor.fetchall()
                            complete_message = ''.join(part[0] for part in parts)
                            
                            conn.execute('''UPDATE multipart_sms 
                                          SET processed = 1 
                                          WHERE ref_number = ? AND sender = ? AND modem_name = ?''',
                                       (ref_num, sender, modem_name))
                            conn.execute('''DELETE FROM multipart_sms 
                                          WHERE ref_number = ? AND sender = ? AND modem_name = ? AND processed = 1''',
                                       (ref_num, sender, modem_name))
                            
                            complete_sms = sms
                            complete_sms.text = complete_message
                            self.logger.info(f"Completed multipart message ref {ref_num} from {sender} on {modem_name}")
                            return complete_sms
                        cursor = conn.execute('''SELECT COUNT(*) 
                                               FROM multipart_sms 
                                               WHERE timestamp < datetime('now', '-30 minutes') AND processed = 0''')
                        stale_count = cursor.fetchone()[0]
                        if stale_count > 0:
                            self.logger.warning(f"Found {stale_count} stale multipart SMS parts, cleaning up")
                            self.cleanup_old_multipart()
                    return None
        return sms

    def validate_destination(self, queue_name, destination):
        if not destination:
            return False
        
        modem_names = list(self.modem_handlers.keys())
        email_names = list(self.email_handlers.keys())
        
        if queue_name in modem_names:
            if not re.match(r'^\+\d{6,15}$', destination):
                self.logger.warning(f"Invalid phone number format for destination: {destination}")
                return False
        elif queue_name in email_names:
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', destination):
                self.logger.warning(f"Invalid email format for destination: {destination}")
                return False
        return True

    def apply_rules(self, modem_name, sms):
        self.logger.debug(f"Applying rules to SMS from {modem_name}")
        for rule in self.rules:
            rule_name = rule.get('name', 'unnamed_rule')
            self.logger.debug(f"Checking rule: {rule_name}")
            
            senders = rule.get('sender', [])
            if senders and sms.number not in senders:
                continue
            
            contents = rule.get('content', [])
            if contents and not any(content.lower() in sms.text.lower() for content in contents):
                continue
            
            message = rule.get('message', [sms.text])[0]
            if isinstance(message, list):
                message = message[0]
            if 'encap' in message.lower():
                message = f"Sender: {sms.number}, Time: {sms.time.isoformat()}, Modem: {modem_name}, Message: {sms.text}"
            
            action = rule.get('action', ['reply'])[0].lower()
            queues = rule.get('queue', [modem_name])
            destinations = rule.get('destination', [sms.number] if action == 'reply' else [])

            if action == 'reply':
                for queue_name in queues:
                    if queue_name in self.modem_handlers:
                        self.modem_handlers[queue_name].send_sms(sms.number, message)
                        self.logger.info(f"Rule {rule_name}: Replied to {sms.number} from {queue_name} with message: {message}")
                    else:
                        self.logger.warning(f"Rule {rule_name}: Queue {queue_name} not found for reply")
            elif action == 'forward':
                if not queues:
                    self.logger.warning(f"Rule {rule_name}: No queues defined for forward action")
                    continue
                
                for queue_name in queues:
                    if queue_name in self.api_handlers:
                        self.api_handlers[queue_name].send_api(sms.number, sms.time.isoformat(), message)
                        self.logger.info(f"Rule {rule_name}: Forwarded to API {queue_name} with message: {message}")
                    elif queue_name in self.email_handlers:
                        for dest in destinations:
                            if self.validate_destination(queue_name, dest):
                                self.email_handlers[queue_name].send_email(dest, message)
                                self.logger.info(f"Rule {rule_name}: Forwarded to email {dest} via {queue_name}: {message}")
                    elif queue_name in self.modem_handlers:
                        for dest in destinations:
                            if self.validate_destination(queue_name, dest):
                                self.modem_handlers[queue_name].send_sms(dest, message)
                                self.logger.info(f"Rule {rule_name}: Forwarded to {dest} via {queue_name}: {message}")
                    else:
                        self.logger.warning(f"Rule {rule_name}: Queue {queue_name} not found")
            else:
                self.logger.warning(f"Rule {rule_name}: Unknown action {action}, defaulting to reply")
                for queue_name in queues:
                    if queue_name in self.modem_handlers:
                        self.modem_handlers[queue_name].send_sms(sms.number, message)
                        self.logger.info(f"Rule {rule_name}: Replied to {sms.number} from {queue_name} with message: {message}")

    def cleanup_old_multipart(self):
        with sqlite3.connect(self.db_manager.db_file) as conn:
            conn.execute('''DELETE FROM multipart_sms 
                           WHERE timestamp < datetime('now', '-30 minutes') AND processed = 0''')
        self.logger.debug("Cleaned up old multipart SMS entries (30-minute timeout)")