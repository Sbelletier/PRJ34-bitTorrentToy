#-*- coding:utf-8 -*-
"""
"""
from __future__ import print_function

import time
import socket
import threading


from peer_protocol_utils import *
from threading_utils import Reader_Thread
from wire import *
from torrent_utils import *
from torrent_manager import Torrent_Local_Track
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
from toy_utils import byte_to_ascii, ascii_to_byte, byte_to_int, int_to_byte

class dummy():
    pass

def test_handshake( hosting = False, verbose=True):
    
    if hosting :
        s_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #Create Client
        client = Peer_Tracker(ip='localhost', port=8010, peer_id="-TY1000-0001TOYIMP01")
        #Create Torrent Manager
        torrent_manager = Torrent_Local_Track("peer1/", "libs")
        #
        s_server.bind( (client.ip, client.port) )
        s_server.listen(5)
        print( "server setup" )
        s_remote, address = s_server.accept()
        print( "connection received" )
        #Create peer
        peer = Peer_Tracker(ip=address, port=8010 )
        #Create
        thread = Clientless_Connection_Thread(torrent_manager, s_remote, client, peer, hosting=True)
        thread.verbose = verbose
        thread.start()
        thread.join() #Wait
        
    else:
        s_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #Create Client
        client = Peer_Tracker(ip='127.0.0.1', port=8010, peer_id="-TY1000-0002TOYIMP01")
        print( "client setup" )
        #Create Torrent Manager
        torrent_manager = Torrent_Local_Track("peer2/","libs" )
        #Create Peer
        peer = Peer_Tracker(ip='localhost', port=8010, peer_id="-TY1000-0001TOYIMP01")
        #Connect
        print( "attempting to connect" )
        s_client.connect( (peer.ip, peer.port) )
        #
        print( "connection successful" )
        thread = Clientless_Connection_Thread( torrent_manager, s_client, client, peer )
        thread.verbose = verbose
        thread.start()
        thread.join() #Wait
    #FEEDBACK
    thread.join()
    print( "PEER STATUS: "+ str(thread.peer_download.pieces_downloaded) )
    print( "My Interest: "+ str(thread.am_interested) )
    print( "Peer Interest: "+ str(thread.peer_interested) )
    print( "Peer Interesting Pieces: "+ str(thread.peer_interesting_pieces) )


def test_2_to_1():
    #Setup Host
    host = Peer_Tracker(ip='localhost', port=8010, peer_id="-TY1000-0001TOYIMP01")
    tracker_h = Torrent_Local_Track("peer1/", "libs")
    s_h = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s_h.bind( (host.ip, host.port) )
    s_h.listen(5)
    #Setup Client 1
    client_1 = Peer_Tracker(ip='127.0.0.1', port=8010, peer_id="-TY1000-0010TOYIMP01")
    tracker_c1 = Torrent_Local_Track("peer2/", "libs")
    s_c1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #Setup Client 2
    client_2 = Peer_Tracker(ip='127.0.0.1', port=8010, peer_id="-TY1000-0020TOYIMP01")
    tracker_c2 = Torrent_Local_Track("peer3/", "libs")
    s_c2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #Connection Client 1
    s_c1.connect( (host.ip, host.port) )
    s_r, _ = s_h.accept()
    t_hc1 = Clientless_Connection_Thread(tracker_h, s_r, host, client_1, True)
    t_hc1.verbose = True
    t_hc1.start()
    t_c1h = Clientless_Connection_Thread(tracker_c1, s_c1, client_1, host, False)
    t_c1h.start()
    #Connection Client 2
    s_c2.connect( (host.ip, host.port) )
    s_r2, _ = s_h.accept()
    t_hc2 = Clientless_Connection_Thread(tracker_h, s_r2, host, client_2, True)
    t_hc2.verbose = True
    t_hc2.start()
    t_c2h = Clientless_Connection_Thread(tracker_c2, s_c2, client_2, host, False)
    t_c2h.start()
    #
    t_hc1.join()
    t_c1h.join()
    t_hc2.join()
    t_c2h.join()
    #
    print("Success")



if __name__ == '__main__':
    import sys
    print( sys.argv )
    if len(sys.argv)>1 and sys.argv[1] == "-h":
        test_handshake( hosting=True )
    elif len(sys.argv)>1 and sys.argv[1] == "-m":
        test_2_to_1()
    else:
        test_handshake( hosting=False )