from iot_message.message import Message
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
address = None


def send(msg):
    if address is None:
        raise Exception('Set address')

    message = Message()
    message.set(msg)
    print(message)
    s.sendto(bytes(message), address)
