#-*- coding:utf-8 -*-
"""
Ce fichier contient des utilitaires pour la gestion du Protocole en lui même
"""
from sys import version_info

from toy_utils import byte_to_ascii, byte_to_int, int_to_byte, ascii_to_byte
from toy_utils import LEN_SHA256
"""
===================
    CONSTANTES
===================
"""
"""
GESTION D'HORLOGE
"""
#Note : tous les temps sont en seconde
TICK_DURATION = 0.1
KEEP_ALIVE_PULSE = TICK_DURATION*50
INPUT_TIMEOUT = TICK_DURATION*100
CHOKING_INTERVAL = 5
"""
GESTION DU HANDSHAKE
"""
HANDSHAKE_MAX_TIMEOUT = 10
HANDSHAKE_LENPREF_SIZE = 1
HANDSHAKE_PROTOCOL_ID = bytearray("BITTOY")
"""
GESTION DE MESSAGES
"""
REQ_MAX_LENGTH = 8*1024 #Un peer ne peut pas demander plus de 8Ko a la fois
"""
TRAITEMENT DE REQUETES
"""
#La probabilité peut sembler basse mais les tentatives sont frequentes
#Tenté(es) n fois par tour de boucle
REQ_ACCEPT_PROBA = 0.25 #Probabilité d'accepter une requete
REQ_SEND_PROBA = 0.20 #Probabilité d'envoyer une requete
MIN_RAND_REQ_SIZE = 1024 #Taille minimale d'une requete si la place permet du requetage aléatoire
#Tenté(es) une fois sans retirage possible
REDUCE_SIZ_PROBA = 0.45 #Probabilité de réduire la taille d'une grosse requete
"""
CHOKE/UNCHOKE
"""
#Les probabilités de changer d'état (1 - Threshold) doivent rester
#Faible pour eviter la fibrillation
UNCHOKE_THRESH_DL = 0.8 #
UNCHOKE_THRESH_OPT = 0.9 #Optimist Unchoke
# Les seuils d'unchoke sont plus bas que les seuils de choke
# Dans le but de minimiser les chances de choke tous les threads pendant trop longtemps
CHOKE_THRESH_PES = 0.95 #Pessimist Choke
CHOKE_THRESH_NDL = 0.95 #
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
    Cet objet contient les informations minimales pour identifier un peer lors de l'echange entre
    deux clients

    Attributs :
        - ip : <String> l'adresse du peer
        - port : <Int> le port de connection du peer sur le reseau
        - peer_id : <String> l'identifiant du peer sur le reseau (20 Caracteres)
    """

    def __init__(self, ip, port, peer_id = None):
        """
        Constructeur
        """
        #NOTE_1 : peer_id initialisé à None pour client distant hosté localement
        #NOTE_2 : peer_id forcement initialisé avant la connection pour connection a host distant
        self.ip = ip
        self.port = port
        self.id = peer_id



class Piece_Request():
    """
    Cet objet contient les informations necessaires pour identifier une demande de piece

    Attributs:
        - piece_index : <Int> indice de la pièce demandée
        - begin : <Int> indice de l'emplacement à partir duquel ecrire dans la piece
        - length : <Int> nombre de bytes (octets) demandées
    """
    def __init__(self, piece_index, begin, length):
        """
        Constructeur
        """
        self.piece_index = piece_index
        self.begin = begin
        self.length = length
       

    def __eq__(self, other):
        """
        OPERATEUR ==
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
        OPERATEUR != (different de not == en python)
        """
        if not isinstance(other, Piece_Request) :
            return True
        else :
            test = self.piece_index != other.piece_index
            test = test or self.begin != other.begin
            test = test or self.length != other.length
            return test


class Message():
    """
    Objet representant un message envoyé d'un peer à l'autre

    Attributs :
        - id : <Integer> un id specifique au type de message envoyé (voir Constantes)
        - payload : <None> si le message n'a pas de payload, un <Tuple> sinon
    """
    def __init__(self, msg_id, payload=None ):
        """
        Constructeur
        """
        self.id = msg_id
        self.payload = payload

    def to_byte(self):
        """
        Convertit le message en une chaine de bytes (octets) et renvoie cette chaine

        Retour :
            - Une bytearray(Python 2.X) ou un bytes(Python 3.X) dont le sens sémantique
                est similaire à l'instance appelante
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
    Extension de int_to_byte(integer) assurant les zéros préfixes

    Paramètres Obligatoires :
        - integer : l'entier à convertir en byte
        - size : le nombre (minimal) de byte que doit obligatoirement occuper l'entier

    Retour :
        - une chaine de bytes (octets) codant l'entier pris en entrée sous base 256

    Hypothèse de départ : 
        - integer < 256**size
    """
    seq = int_to_byte( integer )
    while len( seq ) < size :
        seq = int_to_byte( 0 ) + seq
    return seq



def Message_From_Byte( byte ):
    """
    Construit un objet de type Message à partir d'une chaine de bytes

    Paramètres :
        - byte : une chaine de bytes contenant le message

    Retour :
        - Le Message nouvellement construit
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


