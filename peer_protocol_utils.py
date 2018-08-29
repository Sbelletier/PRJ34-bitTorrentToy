#-*- coding:utf-8 -*-
"""
"""
from sys import version_info

from toy_utils import byte_to_ascii, byte_to_int, int_to_byte, ascii_to_byte

"""
===================
    CONSTANTES
===================
"""

#
HANDSHAKE_MAX_TIMEOUT = 10
HANDSHAKE_LENPREF_SIZE = 1
HANDSHAKE_PROTOCOL_ID = bytearray("BITTOY")
"""
"""
#
MSG_LENPREF_SIZE = 4
# Theoriquement Obsolete mais sait on jamais
# MSG_MAX_LENGTH = (2**(8*MSG_LENPREF_SIZE) - 1) + MSG_LENPREF_SIZE #Taille adressable + memoire
REQ_MAX_LENGTH = 8*1024 #Un peer ne peut pas demander plus de 8Ko a la fois
"""
TRAITEMENT DE REQUETES
"""
#La probabilité peut sembler basse mais les tentatives sont frequentes
#Tenté(es) n fois par tour de boucle
REQ_ACCEPT_THRESHOLD = 0.25 #Probabilité d'accepter une requete
REQ_SEND_THRESHOLD = 0.20 #Probabilité d'envoyer une requete
MIN_RAND_REQ_SIZE = 1024 #Taille minimale d'une requete si la place permet du requetage aléatoire
#Tenté(es) une fois sans retirage possible
REDUCE_SIZ_THRESHOLD = 0.45 #Probabilité de réduire la taille d'une grosse requete
"""
TYPES DE MESSAGE
"""
#Maintien
KEEP_ALIVE = -1
#Mise à jour
CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
#Gestion de pieces
HAVE = 4
REQUEST = 6
PIECE = 7
CANCEL = 8
#

HANDLED_MESSAGES = [KEEP_ALIVE, CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED, HAVE, REQUEST, PIECE, CANCEL]


"""
================
    CLASSES
================
"""
class Peer_Tracker():
    """

    """
    def __init__(self, ip, port, peer_id = None):
        #NOTE_1 : peer_id initialisé à none pour client distant hosté localement
        #NOTE_2 : peer_id forcement iniatilisé avant la connection pour connection a host distant
        self.ip = ip
        self.port = port
        self.id = peer_id
        #Initialisation

class Piece_Request():
    """

    """
    def __init__(self, piece_index, begin, length):
        self.piece_index = piece_index
        self.begin = begin
        self.length = length
        #
        self.failure_count = 0

    def __eq__(self, other):
        """
        EQUAL OPERATOR
        """
        if not isinstance(other, Piece_Request) :
            return False
        else :
            test = self.piece_index == other.piece_index
            test = test and self.begin == other.begin
            test = test and self.length == other.length
            return test

    def __ne__(self, other):
        """
        NOT EQUAL OPERATOR
        """
        if not isinstance(other, self) :
            return True
        else :
            test = self.piece_index != other.piece_index
            test = test or self.begin != other.begin
            test = test or self.length != other.length
            return test


class Message():
    """
    Note : Payload is always a Tuple
    """
    def __init__(self, msg_id, payload=None ):
        self.id = msg_id
        self.payload = payload

    def to_byte(self):
        """
        """
        if self.id == KEEP_ALIVE:
            return code_int_on_size(0, 4)
        #CHOKE, UNCHOKE, INTERESTED ET NOT_INTERESTED N'ONT PAS DE PAYLOAD
        elif self.id == CHOKE:
            length = code_int_on_size(1, 4)
            byte_id = code_int_on_size(CHOKE, 1)
            return length + byte_id
        elif self.id == UNCHOKE:
            length = code_int_on_size(1, 4)
            byte_id = code_int_on_size(UNCHOKE, 1)
            return length + byte_id
        elif self.id == INTERESTED:
            length = code_int_on_size(1, 4)
            byte_id = code_int_on_size(INTERESTED, 1)
            return length + byte_id
        elif self.id == NOT_INTERESTED:
            length = code_int_on_size(1, 4)
            byte_id = code_int_on_size(NOT_INTERESTED, 1)
            return length + byte_id
        #HAVE N'A QU'UNE PAYLOAD : PIECE_INDEX
        elif self.id == HAVE:
            length = code_int_on_size(5, 4)
            byte_id = code_int_on_size( HAVE, 1 )
            piece_index = code_int_on_size( self.payload[0], 4 )
            return length + byte_id + piece_index
        #REQUEST A TROIS PAYLOADS : PIECE_INDEX, BEGIN_INDEX, LENGTH
        elif self.id == REQUEST:
            length = code_int_on_size(13, 4)
            byte_id = code_int_on_size( REQUEST, 1 )
            piece_index = code_int_on_size( self.payload[0], 4 )
            begin = code_int_on_size( self.payload[1], 4 )
            p_length = code_int_on_size( self.payload[2], 4 )
            payload = piece_index + begin + p_length
            return length + byte_id + payload
        #PIECE A TROIS PAYLOADS : PIECE_INDEX, BEGIN_INDEX, BLOCK
        elif self.id == PIECE:
            #block est déjà une chaine de byte
            byte = self.payload[2] 
            if version_info < (3, 0):
                block =  bytearray( byte )
            else:
                block = bytes( byte )
            length = code_int_on_size( 9 + len(block), 4)
            byte_id = code_int_on_size( PIECE, 1)
            piece_index = code_int_on_size( self.payload[0], 4 )
            begin = code_int_on_size( self.payload[1], 4 )
            payload = piece_index + begin + block
            return length + byte_id + payload
        #REQUEST A TROIS PAYLOADS : PIECE_INDEX, BEGIN_INDEX, LENGTH
        elif self.id == CANCEL:
            length = code_int_on_size(13, 4)
            byte_id = code_int_on_size( CANCEL, 1 )
            piece_index = code_int_on_size( self.payload[0], 4 )
            begin = code_int_on_size( self.payload[1], 4 )
            p_length = code_int_on_size( self.payload[2], 4 )
            payload = piece_index + begin + p_length
            return length + byte_id + payload




"""
==================
	FONCTIONS
==================
"""
def code_int_on_size(integer, size):
    """
    Hypothèse de départ : 
        - integer < 256**size
    """
    seq = int_to_byte( integer )
    while len( seq ) < size :
        seq = int_to_byte( 0 ) + seq
    return seq



def Message_From_Byte( byte ):
    """
    """
    # On recupere la longueur du message
    msg_len = byte_to_int( byte[:4] )
    # Un message vide est un keep alive
    if msg_len == 0:
        return Message( KEEP_ALIVE )
    # On degage ce qui est lu
    byte = byte[4:]
    # On recupere l'identifiant du message
    msg_id = byte_to_int( byte[0] )
    #On verifie qu'il s'agit d'un message qu'on sait traiter
    if msg_id in HANDLED_MESSAGES:
        #GROS SWITCH
        if msg_id == CHOKE:
            #Cas du CHOKE: <len><id>
            return Message( CHOKE )
        elif msg_id == UNCHOKE:
            #Cas du UNCHOKE: <len><id>
            return Message( UNCHOKE )
        elif msg_id == INTERESTED:
            #Cas du INTERESTED: <len><id>
            return Message( INTERESTED )
        elif msg_id == NOT_INTERESTED:
            #Cas du NOT_INTERESTED: <len><id>
            return Message( NOT_INTERESTED )
        elif msg_id == HAVE:
            # Cas du HAVE : <len><id><piece_index>
            byte = byte[1:] # On degage ce qui est déjà lu
            payload = ( byte_to_int( byte[:4] ), ) #Ici la payload n'a qu'un element (a,) -> tuple 1 elmt
            return Message( HAVE, payload )
        elif msg_id == REQUEST:
            # Cas de REQUEST : <len><id><piece index><begin><length>
            byte = byte[1:]# On degage ce qui est déjà lu
            index = byte_to_int( byte[:4] )
            begin = byte_to_int( byte[4:8] )
            length = byte_to_int( byte[8:12] )
            #Si la requete est trop grosse on la rejete
            if length > REQ_MAX_LENGTH :
                return None
            payload = (index, begin, length)
            return Message( REQUEST, payload )
        elif msg_id == PIECE :
            # Cas de PIECE : <len><id><piece index><begin><block>
            byte = byte[1:]# On degage ce qui est déjà lu
            index = byte_to_int( byte[:4] )
            begin = byte_to_int( byte[4:8] )
            block_s = byte[8:msg_len-1]
            #
            if version_info < (3, 0):
                block =  bytearray( block_s )
            else:
                block = bytes( block_s )

            payload = (index, begin, block)
            return Message( PIECE, payload )
        elif msg_id == CANCEL:
            # Cas de REQUEST : <len><id><piece index><begin><length>
            byte = byte[1:]# On degage ce qui est déjà lu
            index = byte_to_int( byte[:4] )
            begin = byte_to_int( byte[4:8] )
            length = byte_to_int( byte[8:12] )
            payload = (index, begin, length)
            return Message( CANCEL, payload )
    #FIN DU GROS SWITCH        
    return None
