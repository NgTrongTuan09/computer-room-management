import json
import socket
import threading
from utils.activity_db import bulk_insert
from utils.logger import LoggerSetup

logger = LoggerSetup.get_logger(__name__)

# We'll patch the server file to handle ACTIVITY packets inside handle_client loop.
# Read the current server, insert parsing code where on_packet_received is called.
