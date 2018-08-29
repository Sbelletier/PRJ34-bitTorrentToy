
#-*- coding:utf-8 -*-
"""
"""
import socket
import thread


from toy_utils import random_peer_id


"""

"""
class Client():
    
    def __init__(self, port, id, ip=None):
        if not ip:
            self.ip = socket.gethostname()
        else:
            self.ip = ip
        self.active_connections = []
        self.update_stack = []


class Torrent_download():
    pass



if __name__ == '__main__':
    client = Client(8010, random_peer_id(), ip="127.0.0.1")

