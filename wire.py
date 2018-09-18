#-*- coding:utf-8 -*-
from __future__ import print_function
"""
Ce module contient la classe servant à gérer une connection entre le client
et un peer au niveau de l'echange de message selon la norme de Bit Torrent

"""

import time
import socket
import threading
import random


from peer_protocol_utils import *
from threading_utils import Reader_Thread
from torrent_utils import Download_track
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
from toy_utils import byte_to_ascii, ascii_to_byte, byte_to_int, int_to_byte



"""
=======================
     THREAD
=======================
"""
class Connection_Thread(threading.Thread):
    """
    Ce thread s'occupe du maintien et de la communication sur une connection déjà ouverte
    (cad dont le handshake est déjà validé) 

    Attributs :
        - socket : le socket sur lequel la connection est établie
        - master : le client possédant la connection (qu'elle soit entrante ou sortante)
        - manager : le gestionnaire de torrenting (pour le tenir à jour de l'existence de la connexion)
        - track : le suivi du téléchargement local du torrent
        - peer : une representation du peer avec lequel on communique
        - peer_download : une representation de l'état de téléchargement du torrent chez le peer
        - peer_interesting_pieces : les pieces possédées par le peer mais pas par le client
        - am_choking : condition =True si le client choke le peer
        - peer_choking : condition =True si le peer choke le client
        - am_interested : condition =True si le peer a des pieces qui interessent le client
        - peer_interested : condition =True si le client a des pieces qui interessent le peer
        - verbose : Flag set à False par défaut. Si =True, active une trace.
        - reader : Thread lisant sur le socket
        - reading_stack : liste sur laquelle l'instance lit les messages reçus par *reader*
        - updates_stack : liste sur laquelle l'instance lit les messages envoyés par le client
        - msg_stack : liste des messages en attente d'envoi de la part de l'instance
        - pending_peer_requests : requetes en attente de réponse de la part du peer
        - pending_sent_requests : requetes envoyés au peer en attente de réponse
        - last_input_time : date du dernier message reçu du peer (pour du connection timeout)
        - last_output_time : date du dernier message envoyé au peer (pour un eventuel KEEP_ALIVE)
    """

    def __init__(self, track, manager, t_socket, master, peer, reader ):
        """
        Constructeur 

        Paramètres :
            - track : l'objet suivant le téléchargement local du torrent
            - manager : le thread gérant le torrenting du fichier à l'echelle du client
            - t_socket : le socket sur lequel ecouter/envoyer
            - peer : le peer avec lequel s'effectue la connection
            - reader : le thread bloquant sur la lecture de messages du peer
        """
        threading.Thread.__init__(self)
        # NETWORKING
        self.socket = t_socket
        #Local Representation
        self.master = master
        self.manager = manager
        self.manager.register_connection( self, peer )
        self.track = track
        self.track.register_connection( self )
        #Remote Representation
        self.peer = peer
        self.peer_download = Download_track( self.track )
        self.peer_interesting_pieces = []
        #P2P Values
        self.am_choking = True
        self.peer_choking = True
        self.am_interested = False
        self.peer_interested = False
        #Flags
        self.verbose = False
        #Own memory
        self.reader = reader
        self.reading_stack = reader.stack #Branchement de l'input sur la stack
        self.updates_stack = []
        self.msg_stack = []
        
        self.pending_peer_requests = []
        self.pending_sent_requests = [] 

        self.last_input_time = time.time()
        self.last_output_time= time.time()
        



    def run(self):
        """
        BOUCLE D'EXECUTION DU THREAD
        """
        #On envoie toutes les pièces déjà possédées
        #Note : vu qu'on ne gere pas BITFIELD, on envoie plein de HAVE
        for i in range( len (self.track.pieces_downloaded) ) :
            if self.track.pieces_downloaded[i] == True :
                have_msg = Message( HAVE, (i,) )#(i,) -> Tuple à 1 element
                self.socket.send( have_msg.to_byte() )
        #        
        keep_alive = True
        # Boucle de Communication
        while keep_alive :
            #ETAPE 1 : Lecture des messages
            #print ("reading_stack status "+str( len(self.reading_stack) ))
            if len( self.reading_stack ) > 0:
                self.last_input_time = time.time()
            while len(self.reading_stack) > 0:
                bmsg = self.reading_stack.pop(0)
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
                elif update == "SHUTDOWN":
                    keep_alive = False
                elif update == "CHOKE":
                    self.am_choking = True
                    msg = Message( CHOKE )
                    self.msg_stack.append( msg )
                elif update == "UNCHOKE":
                    self.am_choking = False
                    msg = Message( UNCHOKE )
                    self.msg_stack.append( msg )
            #ETAPE 3 : Gestion des requetes
            self.manage_peer_requests()
            #Envoi Probable d'une requete
            if not self.peer_choking and self.am_interested and random.random() < REQ_SEND_PROBA:
                self.prepare_request_to_send()
            #ETAPE 4 : Envoi des messages en attente
            #print( "message_stack status "+str(len(self.msg_stack)))
            #On envoie un keep alive si on risque le timeout
            if len( self.msg_stack ) > 0:
                self.last_output_time = time.time()
            elif time.time() - self.last_output_time > KEEP_ALIVE_PULSE:
                msg = Message( KEEP_ALIVE )
                self.msg_stack.append( msg )
                self.last_output_time = time.time()
            #
            while len(self.msg_stack) > 0 :
                msg = self.msg_stack.pop(0)
                if msg.id == 7 and self.verbose:
                    print( "Sending block from piece "+ str(msg.payload[0]) +"...")
                self.socket.send( msg.to_byte() )
            
            #print( "sleep")
            #ETAPE 5 : SLEEP 
            time.sleep( TICK_DURATION )
            #print "awaken"
            #ETAPE 6 : FINITION SPONTANEE
            if self.peer_download.is_complete() and self.track.is_complete() :
                if self.verbose:
                    print( "Download Complete !")
                keep_alive = False
            if time.time() - self.last_input_time > INPUT_TIMEOUT:
                if self.verbose:
                    print( "Connection Timed out !") 
                keep_alive = False   
        #FIN DE LA PSEUDO BOUCLE INFINIE
        self.terminate() #Terminaison propre
        return



    def manage_message(self, msg ):
        """
        Traite un Message Recu du Peer

        Paramètre :
            - msg : un objet encapsulant le message
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
            if not self.track.pieces_downloaded[ piece_index ]:
                #On l'ajoute à la liste des pieces telechargeable via le peer
                self.peer_interesting_pieces.append( piece_index )
                #On notifie la piece qu'on pourrait lui envoyer des morceaux
                piece = self.track.pieces[ piece_index ]
                piece.may_write.append( self )
                #On verifie si l'interet pour le peer est nouveau
                if not self.am_interested :
                    #Si oui, on le notifie au peer
                    self.am_interested = True
                    interest_msg = Message( INTERESTED )
                    self.msg_stack.append( interest_msg )
            #Fin Case
        elif msg.id == REQUEST :
            if self.verbose:
                print( 'Request Received piece=' + str(msg.payload[0]) + ' begin=' + str(msg.payload[1]) )
            #REQUEST
            #On ignore si on choke
            if not self.am_choking:
                #On enregistre la requete
                request = Piece_Request( *(msg.payload) )#Unpack the tuple directly
                #On enregistre que des requêtes qu'on est susceptible de satisfaire
                if self.track.pieces_downloaded[ request.piece_index ] == True :
                    self.pending_peer_requests.append( request )
            #Fin Case
        elif msg.id == PIECE:
            #On deballe le message
            piece_index, begin, block = msg.payload
            #Recuperation de la longueur
            length = len( block )
            #On tente d'update la piece correspondante
            piece = self.track.pieces[ piece_index ]
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

        Paramètres :
            - piece_index : l'indice de la piece dont on doit annuler les requetes
        """
        for request in self.pending_sent_requests:
            if request.piece_index == piece_index:
                msg = Message(CANCEL, (request.piece_index, request.begin, request.length) )
                self.msg_stack.append( msg )
                self.pending_sent_requests.remove( request )




    def prepare_request_to_send(self):
        """
        Prepare une requete pour le peer

        """
        #Selection d'une piece interessante possédée par le peer aléatoire
        piece_index = random.choice( self.peer_interesting_pieces )
        piece = self.track.pieces[piece_index]
        #On ecrit à l'endroit prevu pour la piece
        begin = piece.write_pos
        #On choisit la longueur aleatoirement
        #Note : généralement on ferait plutot selon la vitesse de la connection
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
        self.msg_stack.append( msg )
        #On time out les requetes trop vieilles comme le ferait le peer
        self.pending_sent_requests = self.pending_sent_requests[-10:]
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
            if random.random() < REQ_ACCEPT_PROBA:
                reduce = False
                #Une grosse requete a des chances de se voir tronquer
                if request.length >= REQ_MAX_LENGTH//2 and random.random() < REDUCE_SIZ_PROBA:
                    request.length = request.length//2
                #On recupere le byte correspondant
                piece = self.track.pieces[ request.piece_index ]
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
                


    def terminate(self):
        """
        Ferme proprement le thread
        """
        #Arret de la socket --> leve une erreur si le peer a déjà fermée la connection
        try:
            self.socket.shutdown( socket.SHUT_WR )  
        except Exception:
            pass
        self.socket.close()
        #On notifie le client que le thread s'est arrete
        self.track.unregister_connection( self )
        self.manager.unregister_connection( self, self.peer )




"""
==========================================

THREAD POUR TESTER LE PROTOCOLE UN POUR UN

==========================================
"""
class Dummy_Client(object):
    """
    Utiliser pour occulter l'absence de client
    """
    def __init__(self):
        pass
    def register_connection(self, connection, peer):
        pass
    def unregister_connection(self, connection, peer):
        pass

class Clientless_Connection_Thread( Connection_Thread ):
    """
    Thread de connection ne necessitant pas de client
    il ne gere pas le choking mais peut faire un handshake si on lui donne les paramètres adéquat
    """

    def __init__(self, torrent_manager, t_socket, master, peer, hosting=False):
        #
        Connection_Thread.__init__(self, torrent_manager, Dummy_Client(), t_socket, master, peer, 
                                reader= Reader_Thread(t_socket=t_socket, stack=[]) )
        self.hosting = hosting #True : Host = client, False : Host = remote
        self.am_choking = False #On enleve le choke vu qu'il n'y a pas de client pour le gerer
        self.peer_choking = False


    def run(self):

        #On Initialise la lecture
        self.reader.start()
        # Handshake normalement géré par le client
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
            if self.verbose:
                print ("HANDSHAKE SUCCEEDED WITH "+self.peer.id)
            Connection_Thread.run(self)
        else:
            if self.verbose:
                print( "HANDSHAKE FAILED")
        self.terminate()

    

    def wait_and_check_handshake(self):
        """
        valide un handshake

        Retour :
            - True si le handshake a reussi, False sinon
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
            if byte_to_ascii( msg[:LEN_SHA256] ) != self.track.info_hash:
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
        handshake += ascii_to_byte( self.track.info_hash )
        #peer_id
        handshake += ascii_to_byte( self.master.id )
        #
        return handshake
    




