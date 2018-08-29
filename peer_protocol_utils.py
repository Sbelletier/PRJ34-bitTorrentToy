#-*- coding:utf-8 -*-
"""
"""

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
MSG_MAX_LENGTH = (2**(8*MSG_LENPREF_SIZE) - 1) + MSG_LENPREF_SIZE #Taille adressable + memoire
REQ_MAX_LENGTH = 8*1024 #Un pair ne peut pas demander plus de 8Ko a la fois
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
        if not isinstance(other, self) :
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

    def to_bytes(self):
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
            byte = byte[1:] # On degage ce qui est lu
            payload = ( byte_to_int( byte ), ) #Ici la payload n'a qu'un element (a,) -> tuple 1 elmt
            return Message( HAVE, payload )
    #FIN DU GROS SWITCH        
    return None
