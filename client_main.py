from network.client import SocketClient


client = SocketClient("127.0.0.1")

client.connect()
client.send_computer_info()
client.start_heartbeat()
client.start_screen_stream()
client.start_receive_loop()
input()