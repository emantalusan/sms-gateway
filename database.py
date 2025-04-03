import sqlite3
import logging

class DatabaseManager:
    def __init__(self, db_file='sms_database.db'):
        self.logger = logging.getLogger(__name__)
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        self.logger.debug("Initializing database")
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS messages
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            modem_name TEXT,
                            sender TEXT,
                            timestamp TEXT,
                            message TEXT)''')
        self.logger.info("Database initialized")

    def save_sms(self, modem_name, sms):
        self.logger.debug(f"Saving SMS to database from {modem_name}")
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('INSERT INTO messages (modem_name, sender, timestamp, message) VALUES (?, ?, ?, ?)',
                        (modem_name, sms.number, sms.time.isoformat(), sms.text))
        self.logger.info(f"Saved SMS from {sms.number} to database from {modem_name}")