import logging
import threading
import time
from datetime import datetime
from collections import defaultdict
from gsmmodem.pdu import Concatenation
import re

class SMSProcessor:
    def __init__(self, memory_store, rules, multipart_timeout_minutes):
        self.logger = logging.getLogger(__name__)
        self.memory_store = memory_store
        self.rules = rules
        self.modem_handlers = {}
        self.email_handlers = {}
        self.api_handlers = {}
        self.multipart_store = defaultdict(list)  # { (sender, ref_num, modem_name): [(part_num, text, timestamp, total_parts), ...] }
        self.multipart_lock = threading.Lock()
        self.timeout_seconds = multipart_timeout_minutes * 60  # Convert minutes to seconds
        self.immediate_processing = self.timeout_seconds == 0  # Flag for immediate processing
        if not self.immediate_processing:
            self.start_cleanup_thread()
        self.logger.debug(f"Initialized SMS processor with multipart timeout {multipart_timeout_minutes} minutes"
                         f"{' (immediate processing enabled)' if self.immediate_processing else ''}")

    def start_cleanup_thread(self):
        """Start a thread to clean up timed-out multipart SMS parts (if timeout > 0)"""
        def cleanup_task():
            while True:
                self.cleanup_timed_out_parts()
                time.sleep(60)  # Check every minute
        thread = threading.Thread(target=cleanup_task, daemon=True, name="Multipart-Cleanup")
        thread.start()
        self.logger.debug("Started multipart cleanup thread")

    def get_multipart_note(self, sender, ref_num, part_num, total_parts):
        """Generate a standard multipart note with sender and part number"""
        return f"\n[Note: Part:{part_num}/{total_parts} Reference:{ref_num} From:{sender}]"

    def cleanup_timed_out_parts(self):
        """Check for multipart SMS parts older than timeout and process them (if timeout > 0)"""
        if self.immediate_processing:
            return
        current_time = time.time()
        with self.multipart_lock:
            for key, parts in list(self.multipart_store.items()):
                if not parts:
                    continue
                sender, ref_num, modem_name = key
                first_timestamp = parts[0][2]
                if current_time - first_timestamp <= self.timeout_seconds:
                    continue
                total_parts = parts[0][3]
                received_parts = len(parts)
                self.logger.warning(f"Timeout reached for multipart SMS from {sender}, ref {ref_num} on {modem_name}: "
                                   f"Received {received_parts}/{total_parts} parts")

                parts.sort(key=lambda x: x[0])  # Sort by part_num for correct message order
                complete_message = ''.join(part[1] for part in parts)
                
                sms = type('SMS', (), {
                    'number': sender,
                    'time': datetime.fromtimestamp(first_timestamp),
                    'text': complete_message,
                    'multipart_ref': ref_num,
                    'multipart_total': total_parts,
                    'multipart_part': received_parts
                })()
                
                self.memory_store.save_sms(modem_name, sms)
                self.apply_rules(modem_name, sms)
                self.logger.info(f"Processed timed-out multipart message ref {ref_num} from {sender} on {modem_name}")
                del self.multipart_store[key]

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
            self.memory_store.save_sms(modem_name, complete_sms)
            self.apply_rules(modem_name, complete_sms)

    def handle_multipart(self, modem_name, sms):
        """Handle multipart SMS and return complete message if ready"""
        sender = sms.number
        timestamp = time.time()

        if not hasattr(sms, 'udh') or not sms.udh:
            return sms

        for udh_element in sms.udh:
            if not isinstance(udh_element, Concatenation):
                continue
            ref_num = udh_element.reference
            total_parts = udh_element.parts
            part_num = udh_element.number
            key = (sender, ref_num, modem_name)
            
            self.logger.debug(f"Multipart SMS on {modem_name} from {sender} - Ref: {ref_num}, Part: {part_num}/{total_parts}")
            
            with self.multipart_lock:
                if self.immediate_processing:
                    complete_sms = type('SMS', (), {
                        'number': sender,
                        'time': sms.time,
                        'text': sms.text,
                        'multipart_ref': ref_num,
                        'multipart_total': total_parts,
                        'multipart_part': part_num
                    })()
                    self.logger.info(f"Immediately processed multipart SMS part ref {ref_num}, part {part_num}/{total_parts} from {sender} on {modem_name}")
                    return complete_sms
                
                if any(p[0] == part_num for p in self.multipart_store[key]):
                    self.logger.warning(f"Duplicate multipart SMS part detected: {sender}, ref {ref_num}, part {part_num}")
                    return None
                
                if key not in self.multipart_store:
                    complete_sms = type('SMS', (), {
                        'number': sender,
                        'time': sms.time,
                        'text': sms.text,
                        'multipart_ref': ref_num,
                        'multipart_total': total_parts,
                        'multipart_part': part_num
                    })()
                    self.logger.info(f"Processed late-arriving multipart part ref {ref_num}, part {part_num}/{total_parts} from {sender} on {modem_name}")
                    return complete_sms
                
                self.multipart_store[key].append((part_num, sms.text, timestamp, total_parts))
                
                if len(self.multipart_store[key]) == total_parts:
                    self.logger.debug(f"All parts received for ref {ref_num} from {sender} on {modem_name}")
                    parts = sorted(self.multipart_store[key], key=lambda x: x[0])
                    complete_message = ''.join(part[1] for part in parts)
                    
                    complete_sms = type('SMS', (), {
                        'number': sender,
                        'time': sms.time,
                        'text': complete_message
                    })()
                    
                    del self.multipart_store[key]
                    self.logger.info(f"Completed multipart message ref {ref_num} from {sender} on {modem_name}")
                    return complete_sms
            return None

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
            
            # Prepare message for API/SMTP
            api_smtp_message = sms.text
            
            # Handle encap format for API/SMTP
            if 'encap' in message.lower():
                try:
                    api_smtp_message = f"Sender: {sms.number}@{modem_name}\nTime: {sms.time.isoformat()}\nMessage:\n{api_smtp_message}"
                except AttributeError as e:
                    self.logger.error(f"Failed to format message for rule {rule_name}: {e}")
                    api_smtp_message = f"Sender: {sms.number}@{modem_name}\nTime: Unknown\nMessage:\n{api_smtp_message}"
            
            # Add multipart note for API/SMTP if applicable
            if hasattr(sms, 'multipart_ref'):
                part_num = getattr(sms, 'multipart_part', None)
                api_smtp_message += self.get_multipart_note(sms.number, sms.multipart_ref, part_num, sms.multipart_total)
            
            action = rule.get('action', ['reply'])[0].lower()
            queues = rule.get('queue', [modem_name])
            destinations = rule.get('destination', [sms.number] if action == 'reply' else [])

            if action == 'reply':
                for queue_name in queues:
                    if queue_name in self.modem_handlers:
                        self.modem_handlers[queue_name].send_sms(sms.number, sms.text)
                        self.logger.info(f"Rule {rule_name}: Replied to {sms.number} from {queue_name} with message: {sms.text}")
                    else:
                        self.logger.warning(f"Rule {rule_name}: Queue {queue_name} not found for reply")
            elif action == 'forward':
                if not queues:
                    self.logger.warning(f"Rule {rule_name}: No queues defined for forward action")
                    continue
                
                for queue_name in queues:
                    if queue_name in self.api_handlers:
                        self.api_handlers[queue_name].send_api(sms.number, sms.time.isoformat(), api_smtp_message)
                        self.logger.info(f"Rule {rule_name}: Forwarded to API {queue_name} with message: {api_smtp_message}")
                    elif queue_name in self.email_handlers:
                        email_message = api_smtp_message if 'encap' in rule.get('message', [''])[0].lower() else api_smtp_message
                        for dest in destinations:
                            if self.validate_destination(queue_name, dest):
                                self.email_handlers[queue_name].send_email(dest, email_message)
                                self.logger.info(f"Rule {rule_name}: Forwarded to email {dest} via {queue_name}: {email_message}")
                    elif queue_name in self.modem_handlers:
                        for dest in destinations:
                            if self.validate_destination(queue_name, dest):
                                self.modem_handlers[queue_name].send_sms(dest, sms.text)
                                self.logger.info(f"Rule {rule_name}: Forwarded to {dest} via {queue_name}: {sms.text}")
                    else:
                        self.logger.warning(f"Rule {rule_name}: Queue {queue_name} not found")
            else:
                self.logger.warning(f"Rule {rule_name}: Unknown action {action}, ignoring.")