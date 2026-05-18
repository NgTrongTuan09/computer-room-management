import time


class Computer:

    def __init__(
        self,
        client_id,
        name,
        ip,
        status,
        ping
    ):
        
        self.client_id = client_id
        self.name = name
        self.ip = ip
        self.status = status
        self.ping = ping
        self.last_heartbeat = time.time()