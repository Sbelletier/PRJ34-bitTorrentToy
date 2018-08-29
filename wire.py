#-*- coding:utf-8 -*-
"""
"""
from __future__ import print_function


import time
import socket
import threading
import random


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
                print( e.message )
                keep_alive = False
            
            


"""
=======================
     THREAD
=======================
"""
class Connection_Thread(threading.Thread):

    def __init__(self, torrent_manager, t_socket, master, peer, hosting=False):
        threading.Thread.__init__(self)
        # NETWORKING
        self.hosting = hosting #True : Host = client, False : Host = remote
        self.socket = t_socket
        #Local Representation
        self.master = master
        self.download = torrent_manager
        self.download.register_connection( self )
        #Remote Representation
        self.peer = peer
        self.peer_download = Download_track( self.download )
        self.peer_interesting_pieces = []
        #P2P Values
        self.am_choking = False
        self.peer_choking = False
        """
        TODO Change back
        self.am_choking = True
        self.peer_choking = True
        """
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
            print ("HANDSHAKE SUCCEEDED WITH "+self.peer.id)
            """
            On envoie toutes les pièces déjà possédées
            Note : vu qu'on ne gere pas BITFIELD, on envoie plein de HAVE
            """
            #TODO remove queue temporaire pour gagner du temps
            queue_msgs = []
            for i in range( len (self.download.pieces_downloaded) ) :
                if self.download.pieces_downloaded[i] == True :
                    have_msg = Message( HAVE, (i,) )#(i,) -> Tuple à 1 element
                    self.socket.send( have_msg.to_byte() )
            #self.socket.send( "done" )
            #        
            keep_alive = True
            # Boucle de Communication
            while keep_alive :
                #ETAPE 1 : Lecture des messages
                #print ("reading_stack status "+str( len(self.reading_stack) ))
                while len(self.reading_stack) > 0:
                    bmsg = self.reading_stack.pop(0)
                    """
                    NOTE TEMPORARY END CONDITION
                    """
                    if bmsg == "done":
                        keep_alive = False
                    else:
                        msg = Message_From_Byte(bmsg)
                        if msg :
                            #Si le message est legal
                            self.manage_message( msg )
                #ETAPE 2 : Lecture des updates
                while len(self.updates_stack) > 0:
                    update = self.updates_stack.pop(0)
                    if type( update ) == int or type( update ) == long:
                        #Si c'est un int c'est l'index dune piece
                        #Si elle fait partie des pieces que le peer pouvait proposer
                        if update in self.peer_interesting_pieces:
                            #On l'enleve de la liste car on l'a déjà
                            self.peer_interesting_pieces.remove(update)
                            #Si le peer n'a plus de pieces interessantes
                            if len( self.peer_interesting_pieces ) == 0 :
                                #On se met à jour et on lui fait signe
                                self.am_interested = False
                                self.msg_stack.append( Message(NOT_INTERESTED) )
                        #Quoiqu'il en soit on le tient au courant
                        msg = Message( HAVE, (update,) )
                        self.msg_stack.append( msg )
                #ETAPE 3 : Gestion des requetes
                self.manage_peer_requests()
                #Envoi Probable d'une requete
                if not self.peer_choking and self.am_interested and random.random() < REQ_SEND_THRESHOLD:
                    self.prepare_request_to_send()
                #ETAPE 4 : Choking/Unchoking
                #ETAPE X : Envoi des messages en attente
                #print( "message_stack status "+str(len(self.msg_stack)))
                while len(self.msg_stack) > 0 :
                    msg = self.msg_stack.pop(0)
                    if msg.id == 7:
                        print( "Sending block from piece "+ str(msg.payload[0]) +"...")
                    self.socket.send( msg.to_byte() )
                
                #print( "sleep")
                #ETAPE X+1 : SLEEP 
                time.sleep( 0.1 )
                #print "awaken"
                if self.peer_download.is_complete() and self.download.is_complete() :
                    print( "Download Complete !")
                    keep_alive = False

        #TODO REMOVE OR LOG
        else:
            print( "HANDSHAKE FAILED")
        
        self.terminate()
        
        
        return



    def manage_message(self, msg ):
        """
        """
        #print( "Message "+str(msg.id) )
        # GROS SWITCH BEGINS
        if msg.id == KEEP_ALIVE :
            pass
        elif msg.id == CHOKE :
            #CHOKE
            #On met à jour notre representation du peer
            self.peer_choking = True
        elif msg.id == UNCHOKE :
            #UNCHOKE
            #On met à jour notre representation du peer
            self.peer_choking = False
        elif msg.id == INTERESTED :
            #INTERESTED
            #On met à jour notre representation du peer
            self.peer_interested = True
        elif msg.id == NOT_INTERESTED :
            #NOT_INTERESTED
            #On met à jour notre representation du peer
            self.peer_interested = False
        elif msg.id == HAVE :
            #HAVE 
            #On met à jour notre representation du peer
            piece_index = msg.payload[0]
            self.peer_download.pieces_downloaded[ piece_index ] = True
            #On regarde si la piece nous interesse
            if not self.download.pieces_downloaded[ piece_index ]:
                #On l'ajoute à la liste des pieces telechargeable via le peer
                self.peer_interesting_pieces.append( piece_index )
                #On notifie la piece qu'on pourrait lui envoyer des morceaux
                piece = self.download.pieces[ piece_index ]
                piece.may_write.append( self )
                #On verifie si l'interet pour le peer est nouveau
                if not self.am_interested :
                    #Si oui, on le notifie au peer
                    self.am_interested = True
                    interest_msg = Message( INTERESTED )
                    self.msg_stack.append( interest_msg )
            #Fin Case
        elif msg.id == REQUEST :
            print( 'Request Received piece=' + str(msg.payload[0]) + ' begin=' + str(msg.payload[1]) )
            #REQUEST
            #On ignore si on choke
            if not self.am_choking:
                #On enregistre la requete
                request = Piece_Request( *(msg.payload) )#Unpack the tuple directly
                #On enregistre que des requêtes qu'on est susceptible de satisfaire
                if self.download.pieces_downloaded[ request.piece_index ] == True :
                    self.pending_peer_requests.append( request )
            #Fin Case
        elif msg.id == PIECE:
            #On deballe le message
            piece_index, begin, block = msg.payload
            #Recuperation de la longueur
            length = len( block )
            #On tente d'update la piece correspondante
            piece = self.download.pieces[ piece_index ]
            if piece.write( begin, block, self.ident ) :
                #Si ca s'est bien passé
                for request in self.pending_sent_requests :
                    #On enleve toutes les requetes susceptible d'aboutir à la meme demande
                    if request.piece_index == piece_index:
                        self.pending_sent_requests.remove( request )
            #Fin Case
        elif msg.id == CANCEL:
            #On recupere le type de requete a annuler
            model = Piece_Request( *(msg.payload) )
            #On annule les requetes qu'on a pas déjà traité qui correspondent
            for request in self.pending_peer_requests :
                if request == model :
                        self.pending_peer_requests.remove( request )




    def cancel_sent_requests(self, piece_index):
        """
        Envoie un cancel pour toute requete non recue sur la piece donnée
        """
        for request in self.pending_sent_requests:
            if request.piece_index == piece_index:
                msg = Message(CANCEL, (request.piece_index, request.begin, request.length) )
                msg_stack.append( msg )
                self.pending_sent_requests.remove( request )




    def prepare_request_to_send(self):
        """
        Prepare une requete pour le peer
        """
        #Select a random in interesting piece
        piece_index = random.choice( self.peer_interesting_pieces )
        piece = self.download.pieces[piece_index]
        #On ecrit à l'endroit prevu pour la piece
        begin = piece.write_pos
        #On choisit la longueur aleatoirement
        max_length = min( REQ_MAX_LENGTH, piece.length - piece.write_pos)
        length = 0
        if max_length <= MIN_RAND_REQ_SIZE :
            length = max_length
        else: 
            length = random.randint( MIN_RAND_REQ_SIZE, max_length)
        #Preparation de la requete
        msg = Message( REQUEST, (piece_index, begin, length) )
        #Ajout aux stacks interessées
        self.pending_sent_requests.append( Piece_Request(piece_index, begin, length) )
        #On time out les requetes trop vieilles comme le ferait le peer
        self.pending_sent_requests = self.pending_sent_requests[-10:]
        self.msg_stack.append( msg )
        #



    def manage_peer_requests(self):
        """
        Prepare une réponse à une requete du peer
        Note : peut decider de faire patienter le peer ou d'envoyer moins de bits que demandé
        """
        #On time out les requetes trop vieilles
        self.pending_peer_requests = self.pending_peer_requests[-10:]
        for request in self.pending_peer_requests:
            #Chaque Requete a une chance aleatoire d'etre acceptée
            if random.random() < REQ_ACCEPT_THRESHOLD:
                reduce = False
                #Une grosse requete a des chances de se voir tronquer
                if request.length >= REQ_MAX_LENGTH//2 and random.random() < REDUCE_SIZ_THRESHOLD:
                    request.length = request.length//2
                #On recupere le byte correspondant
                piece = self.download.pieces[ request.piece_index ]
                byte = piece.read( request.begin, request.length )
                #On verifie que la lecture a fonctionne
                if byte:
                    #On prepare le message à envoyer
                    msg = Message(PIECE, (request.piece_index, request.begin, byte) )
                    self.msg_stack.append( msg )
                    #On enleve la requete des requetes en attentes (elle vient d'etre traitee)
                    self.pending_peer_requests.remove( request )
                    #On n'envoie qu'une requete à la fois 
                    return
                



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
        handshake += ascii_to_byte( self.master.id )
        #
        return handshake



    def terminate(self):
        """
        """
        #Network shutdown
        self.socket.shutdown( socket.SHUT_WR ) 
        self.socket.close()
        #Local shutdown
        self.download.unregister_connection( self )







    




