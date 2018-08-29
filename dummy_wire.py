#-*- coding:utf-8 -*-
"""
"""
from __future__ import print_function

import time
import socket
import threading


from peer_protocol_utils import *
from wire import *
from torrent_utils import *
from torrent_manager import Torrent_manager
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
from toy_utils import byte_to_ascii, ascii_to_byte, byte_to_int, int_to_byte

class dummy():
    pass

def test_handshake( hosting = False):
    
    if hosting :
        s_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #Create Client
        client = Peer_Tracker(ip='localhost', port=8010, peer_id="-TY1000-0001TOYIMP01")
        #Create Torrent Manager
        torrent_manager = Torrent_manager("peer1/", "libs")
        #
        s_server.bind( (client.ip, client.port) )
        s_server.listen(5)
        print( "server setup" )
        s_remote, address = s_server.accept()
        print( "connection received" )
        #Create peer
        peer = Peer_Tracker(ip=address, port=8010 )
        #Create
        thread = Connection_Thread(torrent_manager, s_remote, client, peer, hosting=True)
        thread.start()
        thread.join() #Wait
        
    else:
        s_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #Create Client
        client = Peer_Tracker(ip='127.0.0.1', port=8010, peer_id="-TY1000-0002TOYIMP01")
        print( "client setup" )
        #Create Torrent Manager
        torrent_manager = Torrent_manager("peer2/","libs" )
        #Create Peer
        peer = Peer_Tracker(ip='localhost', port=8010, peer_id="-TY1000-0001TOYIMP01")
        #Connect
        print( "attempting to connect" )
        s_client.connect( (peer.ip, peer.port) )
        #
        print( "connection successful" )
        thread = Connection_Thread( torrent_manager, s_client, client, peer )
        thread.start()
        thread.join() #Wait
    #FEEDBACK
    thread.join()
    print( "PEER STATUS: "+ str(thread.peer_download.pieces_downloaded) )
    print( "My Interest: "+ str(thread.am_interested) )
    print( "Peer Interest: "+ str(thread.peer_interested) )
    print( "Peer Interesting Pieces: "+ str(thread.peer_interesting_pieces) )




if __name__ == '__main__':
    import sys
    print( sys.argv )
    if len(sys.argv)>1 and sys.argv[1] == "-h":
        test_handshake( hosting=True )
    else:
        test_handshake( hosting=False )