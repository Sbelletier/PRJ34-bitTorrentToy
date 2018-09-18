#-*- coding:utf-8 -*-
from __future__ import print_function
"""
Ce module contient des threads utilitaires, potentiellement appelés par d'autres threads
"""

import threading
import socket
import time

from toy_utils import *
from peer_protocol_utils import HANDSHAKE_MAX_TIMEOUT, HANDSHAKE_LENPREF_SIZE, HANDSHAKE_PROTOCOL_ID
from peer_protocol_utils import Peer_Tracker

import bencoding




class Reader_Thread( threading.Thread ):
    """
    Thread dont la vie consiste a bloquer sur de la lecture de socket
    Etant donné que :
        1. my_socket.recv(...) est un appel bloquant
        2. si il y a un my_socket.recv(...) bloqué dans un autre thread
            on peut quand meme faire my_socket.send(...)
    Ce thread sert à bloquer sur l'appel et à tenir son parent informé
    des messages envoyés via une stack

    Attributs
        - socket : le socket sur lequel le thread ecoute
        - stack : la pile sur laquelle le thread ajoute les messages qu'il lit
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
                #print( e.message )
                keep_alive = False
            
"""

"""
class Connection_Listener_Thread( threading.Thread ):
    """
    Thread chargé d'accepter et de dispatcher les connections entrantes

    Attributs :
        - master : Le client qui possède la connection
        - socket : le socket sur lequel receptionner les connections entrantes
    """
    def __init__(self, t_socket, master):
        """
        Paramètres :
            - t_socket : le socket sur lequel l'instance va ecouter
            - master : le client ayant crée l'instance
        """
        threading.Thread.__init__(self)
        self.master = master
        self.socket = t_socket

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
                #NOTE cet appel devrait lever une erreur quand le socket est ferme
                #       pourtant ce n'est pas le cas
                s_remote, address = self.socket.accept()
                peer = Peer_Tracker( ip=address[0], port=self.master.port )
                reader = Reader_Thread(t_socket=s_remote, stack=[])
                reader.start()
                #
                torrent_thread = self.get_thread_for_valid_handshake(peer, reader.stack)
                if torrent_thread and torrent_thread.is_alive():
                    s_remote.send( torrent_thread.get_handshake() )
                    torrent_thread.receive_connection( s_remote, peer, reader )
                else:
                    raise Exception("Thread is dead")

            except Exception as e:
                keep_alive = False
                break
            
                
                

    def get_thread_for_valid_handshake(self, peer, reading_stack):
        """
        Paramètres :
            - peer : le peer essayant d'entrer en contact avec le client
            - reading_stack : la stack ou lire les messages envoyés par le peer

        Retour :
            - Si le torrent mentionné par le handshake est traité par le client de l'instance,
                le thread interne qui s'occupe de ce torrent. Quelque chose qui s'evalue en
                False sinon. Quelque chose qui s'evalue en False si le handshake a échoué.

        Note : Un client ne verifie le handshake que d'une connection sortante
        """
        msg_received = False
        timeout = HANDSHAKE_MAX_TIMEOUT
        begin_time = time.time()
        msg = ""
        while time.time() - begin_time < timeout and not msg_received:
            #Si on a un message
            if len( reading_stack ) > 0:
                msg_received = True
                msg = reading_stack.pop(0)
        if msg_received:
            #Message est une liste de bytes
            #Longueur du Protocol Id [pstrlen]
            protocol_strlen = byte_to_int( msg[0] )
            msg = msg[1:]
            #Protocol Id [pstr] (on segregue les protocoles inattendus) 
            # -> normalement on attendrait pstrlen=19 et pstr="BitTorrent protocol"
            if msg[:protocol_strlen] != HANDSHAKE_PROTOCOL_ID:
                return False
            msg = msg[protocol_strlen:]
            #Reserved Bit -> on ne supporte pas de protocole additionnel
            if byte_to_int(msg[:8]) != 0:
                return False
            msg = msg[8:]
            """
            Moment clé : Redirection de l'info_hash
            """
            target_torrent = None
            #info_hash
            incoming_hash = byte_to_ascii( msg[:LEN_SHA256] )
            if not incoming_hash in self.master.torrent_dict :
                return False
            else:
                target_torrent = self.master.torrent_dict[incoming_hash]
            msg = msg[LEN_SHA256:]
            #peer_id
            #Un hote a verifié tout ce qu'il a à verifier
            peer.id = byte_to_ascii( msg )
            return target_torrent
            
        #Defaut : echec
        return False


        
            
