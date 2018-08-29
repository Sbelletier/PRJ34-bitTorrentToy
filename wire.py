#-*- coding:utf-8 -*-
"""
"""

import time
import socket
import threading


from peer_protocol_utils import *
from torrent_utils import Download_track
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
from toy_utils import byte_to_ascii, ascii_to_byte, byte_to_int, int_to_byte

"""
=======================
    UTILITY THREADS
=======================
"""
class Reader_Thread( threading.Thread ):
    """
    Thread dont la vie consiste a bloquer sur de la lecture de socket
    Etant donné que :
        1. my_socket.recv(...) est un appel bloquant
        2. si il y a un my_socket.recv(...) bloqué dans un autre thread
            on peut quand meme faire my_socket.send(...)
    Ce thread sert à bloquer sur l'appel et à tenir son parent informé
    des messages envoyés via une stack
    """

    def __init__(self, t_socket=None, stack=None):
        """
        Constructeur

        Paramètres :
            - t_socket : le socket sur lequel lire des messages
            - stack : la pile sur laquelle empiler les messages lus
        """
        threading.Thread.__init__(self)
        self.socket = t_socket
        self.stack = stack

    def run(self):
        """
        Boucle d'execution du thread
        """
        keep_alive = True #Variable de controle
        #Boucle pseudo-infinie
        while keep_alive:
            #On gere un shutdown
            try:
                #Appel Bloquant
                data = self.socket.recv(32*1024)
                #Cas ou la connection est fermée
                if data == "":
                    #On arrete le thread 
                    keep_running = False
                else:
                    #On envoie sur la pile
                    self.stack.append( data )
            except Exception as e:
                print e.message
                keep_alive = False
            
            


"""
=======================
     THREAD
=======================
"""
class Connection_Thread(threading.Thread):

    def __init__(self, torrent_manager, t_socket, client, peer, hosting=False):
        threading.Thread.__init__(self)
        # NETWORKING
        self.hosting = hosting #True : Host = client, False : Host = remote
        self.socket = t_socket
        #Local Representation
        self.client = client
        self.download = torrent_manager
        #Remote Representation
        self.peer = peer
        self.peer_download = Download_track( self.download )
        self.peer_interesting_pieces = []
        #P2P Values
        self.am_choking = True
        self.peer_choking = True
        self.am_interested = False
        self.peer_interested = False
        #Own memory
        self.reading_stack = []
        self.updates_stack = []
        self.msg_stack = []
        
        self.pending_peer_requests = []
        self.pending_sent_requests = [] 
        



    def run(self):
        #On Initialise la lecture
        reader = Reader_Thread(t_socket=self.socket, stack=self.reading_stack)
        reader.start()
        # Handshake
        handshake_successful = False
        if self.hosting :
            if self.wait_and_check_handshake() :
                self.socket.send( self.get_handshake() )
                handshake_successful = True
        else:
            self.socket.send( self.get_handshake() )
            handshake_successful = self.wait_and_check_handshake()
        #fin du handshake
        if handshake_successful:
            #TODO REMOVE OR lOG
            print "HANDSHAKE SUCCEEDED WITH "+self.peer.id
            """
            ETAPE 1 : On envoie toutes les pièces déjà possédées
            Note : vu qu'on ne gere pas BITFIELD, on envoie plein de HAVE
            """
            #TODO remove queue temporaire pour gagner du temps
            queue_msgs = []
            for i in range( len (self.download.pieces_downloaded) ) :
                if self.download.pieces_downloaded[i] == True :
                    have_msg = Message( HAVE, (i,) )#(i,) -> Tuple à 1 element
                    # self.socket.send( have_msg.to_bytes() )
                    queue_msgs.append(have_msg)
            #self.socket.send( "done" )
            queue_msgs.append("done")
            print "queue ready"
            #        
            keep_alive = True
            # Boucle de Communication
            while keep_alive :
                #ETAPE 1 : lecture des messages
                print "reading_stack status "+str( len(self.reading_stack) )
                while len(self.reading_stack) > 0:
                    bmsg = self.reading_stack.pop(0)
                    """
                    NOTE TEMPORARY END CONDITION
                    """
                    if bmsg == "done":
                        keep_alive = False
                    else:
                        self.manage_message( Message_From_Byte(bmsg) )
                #ETAPE 2 : 

                #ETAPE X : Envoi des messages en attente
                print "message_stack status "+str(len(self.msg_stack))
                for msg in self.msg_stack :
                    self.socket.send( msg.to_bytes() )
                #Queue artificielle a remove une fois le time out mis en place
                if len( queue_msgs ) > 1:
                    msg = queue_msgs.pop(0)
                    byte = msg.to_bytes()
                    self.socket.send( byte )
                #
                elif len( queue_msgs ) > 0:
                    self.socket.send( queue_msgs.pop(0) )
                print "sleep"
                #ETAPE X+1 : SLEEP 
                time.sleep( 0.25 )
                print "awaken"

        #TODO REMOVE OR LOG
        else:
            print "HANDSHAKE FAILED"
        self.socket.shutdown( socket.SHUT_WR ) 
        #
        self.socket.close()
        
        
        
        return



    def manage_message(self, msg ):
        """
        """
        print( "Message "+str(msg) )
        # GROS SWITCH BEGINS
        if msg.id == KEEP_ALIVE :
            pass
        elif msg.id == CHOKE :
            #CHOKE
            #--> On met à jour notre representation du peer
            self.peer_choking = True
        elif msg.id == UNCHOKE :
            #UNCHOKE
            #--> On met à jour notre representation du peer
            self.peer_choking = False
        elif msg.id == INTERESTED :
            #INTERESTED
            #--> On met à jour notre representation du peer
            self.peer_interested = True
        elif msg.id == NOT_INTERESTED :
            #NOT_INTERESTED
            #--> On met à jour notre representation du peer
            self.peer_interested = False
        elif msg.id == HAVE :
            #HAVE 
            #--> On met à jour notre representation du peer
            piece_index = msg.payload[0]
            self.peer_download.pieces_downloaded[ piece_index ] = True
            #On regarde si la piece nous interesse
            if not self.download.pieces_downloaded[ piece_index ]:
                #On l'ajoute à la liste des pieces telechargeable via le peer
                self.peer_interesting_pieces.append( piece_index )
                #On verifie si l'interet pour le peer est nouveau
                if not self.am_interested :
                    #Si oui, on le notifie au peer
                    self.am_interested = True
                    interest_msg = Message( INTERESTED )
                    self.msg_stack.append( interest_msg )
            #


    def cancel_requests(self, piece_index):
        """
        Envoie un cancel pour toute requete sur la piece donnée
        """
        pass

    def wait_and_check_handshake(self):
        """
        """
        msg_received = False
        timeout = HANDSHAKE_MAX_TIMEOUT
        begin_time = time.time()
        msg = ""
        while time.time() - begin_time < timeout and not msg_received:
            #Si on a un message
            if len( self.reading_stack ) > 0:
                msg_received = True
                msg = self.reading_stack.pop(0)
        if msg_received:
            #Message est une liste de bytes
            #Longueur du Protocol Id [pstrlen]
            protocol_strlen = byte_to_int( msg[0] )
            msg = msg[1:]
            #Protocol Id [pstr] (on segregue les protocole inattendus) 
            # -> normalement on attendrait pstrlen=19 et pstr="BitTorrent protocol"
            if msg[:protocol_strlen] != HANDSHAKE_PROTOCOL_ID:
                return False
            msg = msg[protocol_strlen:]
            #Reserved Bit -> on ne supporte pas de protocole additionnel
            if byte_to_int(msg[:8]) != 0:
                return False
            msg = msg[8:]
            #info_hash
            if byte_to_ascii( msg[:LEN_SHA256] ) != self.download.info_hash:
                return False
            msg = msg[LEN_SHA256:]
            #peer_id
            #Un hote a verifié tout ce qu'il a à verifier
            if self.hosting :
                self.peer.id = byte_to_ascii( msg )
                return True
            #Pour un client -> verification qu'on est connecté a la bonne machine
            elif self.peer.id == byte_to_ascii( msg ):
                return True
        #Defaut : echec
        return False
            
   

    def get_handshake(self):
        """
        """
        #Protocol
        handshake = int_to_byte( len(HANDSHAKE_PROTOCOL_ID) ) + HANDSHAKE_PROTOCOL_ID
        #Reserved
        handshake += bytearray(8)
        #info_hash
        handshake += ascii_to_byte( self.download.info_hash )
        #peer_id
        handshake += ascii_to_byte( self.client.id )
        #
        return handshake







    




