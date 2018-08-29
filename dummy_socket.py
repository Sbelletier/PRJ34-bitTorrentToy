#-*- coding:utf-8 -*-
"""
"""
from __future__ import print_function

import threading
import socket
from time import sleep
from copy import copy

class Reader_Thread( threading.Thread ):

    def __init__(self, t_socket=None, stack=None, id=1):
        
        threading.Thread.__init__(self)
        self.socket = t_socket
        self.stack = stack
        self.id = id

    def run(self):
        keep_running = True
        while keep_running:
            data = self.socket.recv(4096)
            if data == "":
                keep_running = False
            else:
                self.stack.append( data )
        print( "Thread "+ str(self.id) +" shutting down.. stack state "+ str(self.stack) )

def read_thread(s, stack):
    stack.append( s.recv(4096) )
    return 



s_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

stack = []

s_server.bind(('localhost',8010))
s_server.listen(5)

s_client.connect( ('localhost', 8010) )
s_remote, address = s_server.accept()
s_remote = copy(s_remote)
r = Reader_Thread (s_remote, stack) 
r.start()



sleep(2)
s_remote.send("Gimme gimme")

print( s_client.recv(4096) )
s_client.send("data")


###############
#INTERJERCTION D'UN DEUXIEME CLIENT POUR CHECK LES CONFLITS
s_client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
stack2 = []
s_client2.connect(('localhost', 8010))
s_remote2, address = s_server.accept()
r2 = Reader_Thread (s_remote2, stack2, id=2) 
r2.start()

s_client2.send("1")
s_client2.send("23")
s_client2.send("45")

#############

s_client.send("data2")
s_client.send("data3")
while len( stack ) < 1:
    print ("slumber...")
print (stack)
print (stack2)


s_client.close()
sleep(0.30) #Pour le confort du print
s_client2.close()