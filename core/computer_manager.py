from models.computer import Computer


class ComputerManager:

    def __init__(self):
        self.computers = []

    def load_demo_data(self):

        self.computers = [

        Computer(
            "demo-1",
            "PC-01",
            "192.168.1.10",
            "Online",
            "2ms"
        ),

        Computer(
            "demo-2",
            "PC-02",
            "192.168.1.11",
            "Offline",
            "-"
        ),

        Computer(
            "demo-3",
            "PC-03",
            "192.168.1.12",
            "Online",
            "5ms"
        )
    ]

    def get_all_computers(self):
        return self.computers

    def add_computer(self, computer):
        self.computers.append(computer)

    def remove_computer_by_ip(self, ip):

        for computer in self.computers:

            if computer.ip == ip:
                self.computers.remove(computer)
                return True

        return False

    def find_computer_by_ip(self, ip):

        for computer in self.computers:

            if computer.ip == ip:
                return computer

        return None

    def update_status(self, ip, status):

        computer = self.find_computer_by_ip(ip)

        if computer:
            computer.status = status
            return True

        return False
    
    def get_computer_by_id(self, client_id):
        for computer in self.computers:

            if computer.client_id == client_id:
                return computer

        return None