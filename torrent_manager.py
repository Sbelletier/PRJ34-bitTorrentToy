#-*- coding:utf-8 -*-
from __future__ import print_function
from future.standard_library import install_aliases
install_aliases()
"""
Ce module contient des classes pour :
    - Gerer de multiples de connection pour un même torrent (classe Torrenting_Thread)
    - Suivre l'evolution du téléchargement local d'un torrent (classe Torrent_Local_Track)
    - Gerer l'ecriture et la lecture dans une piece de torrent (classe Piece_Manager)
"""


#Future imports
import urllib.parse
import urllib.request as request
import urllib.response
import urllib.robotparser
import urllib.error
#Normal imports
import threading
import socket
import time
import random

import os # Gerer les dossier
import io # Lecture bufferisée de fichier

from torrent_utils import Torrent_track, Download_track
from torrent_utils import get_pieces_filename_by_hash, get_torrent_full_size
from toy_utils import *
from peer_protocol_utils import *
from wire import Connection_Thread
from threading_utils import Reader_Thread
import bencoding
import converter

"""

==============================================
                MANAGEMENT
==============================================

"""

class Torrenting_thread( threading.Thread ):
    """
    Thread chargé de maintenir/crée les connections pour toute la durée du torrenting

    Attributs :
        - master : le client ayant lancé le torrenting
        - track : l'instance chargée de suivre le téléchargement local du torrent
        - seeding : Condition =True si le torrent à été complétement téléchargé
        - interval : l'intervalle de temps à attendre avant de contacter le serveur de tracking
        - master_stack : pile de message envoyés par le tracker
        - peer_dict : dictionnaire reliant un peer_id au peer correspondant
        - peer_connections : dictionnaire reliant un peer_id à la connection correspondante
        - peer_timers : dictionnaire reliant un peer_id à la date de son dernier changement d'état
            choke/unchoke (plus un peer est reste longtemps dans un etat plus il est susceptible
            de changer d'état)
        - complete_peers : liste des peers ayant fini leur téléchargement et fermé leur connection
    """
    
    def __init__(self, master, local_track):
        """
        Constructeur

        Paramètres :
            - master : le client ayant lancé le torrenting
            - local_track : l'instance chargée de suivre le téléchargement local du torrent
        """
        threading.Thread.__init__(self)
        self.master = master
        self.track = local_track
        #Flag to know if you are downloading or just seeding
        if local_track.is_complete():
            self.seeding = True
        else:
            self.seeding = False
        #Tracking communication
        self.interval = TRACKER_INTERVAL #Default value
        #Thread Memory
        self.master_stack = []
        self.peer_dict = dict()
        self.peer_connections = dict()
        self.peer_timers = dict()
        self.complete_peers = []


    def run(self):
        """
        BOUCLE D'EXECUTION DU THREAD
        """
        #Clocks
        last_choke_update = time.time() - 2*CHOKING_INTERVAL #Assure le choking
        last_tracker_call = time.time() - 2*self.interval
        # Flags for tracker_event
        first_contact = True
        download_completed = False

        keep_torrenting = True

        while keep_torrenting:
            #ETAPE 1 : CONNECTION A DE NOUVEAUX PEERS
            #Contact tracker
            if time.time() - last_tracker_call > self.interval:
                last_tracker_call = time.time()
                peers = []
                if first_contact :
                    peers = self.contact_tracker("started")
                    first_contact = False
                else :
                    peers = self.contact_tracker()
                #On regarde si on trouve de nouveaux peers
                for peer_dict in peers:
                    #Si on trouve un nouveau peer
                    peer_id = peer_dict["peer_id"]
                    if peer_id not in self.peer_dict and peer_id not in self.complete_peers and peer_id != self.master.id:
                        #On s'y connecte
                        peer = Peer_Tracker(peer_dict["ip"], int(peer_dict["port"]), peer_id=peer_id)
                        #Une connection peut echouer, ce n'est pas fatal
                        try:
                            self.connect_to( peer )
                        except Exception as e:
                            #print(e)
                            self.peer_dict.pop( peer.id, "" )
                            self.peer_connections.pop( peer.id, "" )
                            print(self.master.id + " : Connection Error to "+peer.ip+":"+str(peer.port) 
                                +" : " )
                            print(e)

            #ETAPE 2 : ON LIT LES MESSAGES DE MASTER
            while len( self.master_stack) > 0:
                msg = self.master_stack.pop(0)
                if msg == "SHUTDOWN":
                    keep_torrenting = False
            #ETAPE 2 : GESTION DES CONNECTIONS EXISTANTES 
            #On gere le choking
            #On ne change les propriétés de choking que toutes les 5 secondes
            #Note : En pratique un temps un peu plus long est préconisé (~10 secondes)
            if time.time() - last_choke_update > CHOKING_INTERVAL:
                last_choke_update = time.time()
                """
                Techniquement, On devrait faire ça en fonction des vitesses de connection.
                Je n'ai néanmoins pas le temps de le faire, et étant donné les petits transferts 
                effectués par l'application, on peut généralement les considérer comme
                equivalentes.
                Je vais donc choisir une approche probabilistique basée sur l'interet (comme la
                version officielle) et le temps passé dans cette état (pour eviter le plus possible
                la fibrillation)
                Developpements possibles sur cette version : 
                    - rajouter un unchoke en cas d'interet pour un peer dans l'espoir qu'il reciproque
                        ainsi qu'une mecanique de reciprocité (avec une certaine probabilité)
                """
                for ident in self.peer_connections:
                    connection = self.peer_connections[ident]
                    #Si delta = 0, THRESH**delta = 1 ==> Changement d'état impossible
                    delta = ( time.time() - self.peer_timers[ident] )// CHOKING_INTERVAL
                    change = False
                    if connection.am_choking:
                        #2 Cas : 
                        #1 - Unchoke d'un pair interessé
                        if connection.peer_interested and random.random() > UNCHOKE_THRESH_DL**delta:
                            change = True
                        #2 - Unchoke optimiste
                        elif random.random() > UNCHOKE_THRESH_OPT**delta:
                            change = True
                        if change :
                            self.peer_timers[ident] = time.time()
                            connection.updates_stack.append("UNCHOKE")
                    else:
                        #2 cas :
                        #1 - Choke d'un peer desinteressé
                        if not connection.peer_interested and random.random() > CHOKE_THRESH_NDL**delta:
                            change = True
                        #2 - Choke aléatoire pour liberer de la bande passante
                        elif random.random() > CHOKE_THRESH_PES**delta:
                            change = True
                        if change :
                            self.peer_timers[ident] = time.time()
                            connection.updates_stack.append("CHOKE")

            #On sleep
            time.sleep( TICK_DURATION )
            #Condition nominale d'arret
            if self.seeding and len( self.peer_connections.keys() ) == 0 and len( self.complete_peers ) > 0:
                keep_torrenting = False
            if not self.seeding and self.track.is_complete() :
                self.seeding = True
                self.contact_tracker("completed")
        #FIN WHILE
        #On extrait le torrent

        self.terminate()



    def contact_tracker(self, event=None):
        """
        Contacte le tracker pour recuperer les peers pour le torrent tracké

        Paramètres optionnels:
            - event : Une string à envoyer comme clé au paramètre event si il doit être utilisé
                    (cf protocole BitTorrent) 
        
        Retour :
            - La liste des Peers telle que renvoyée par le tracker (cf protocole BitTorrent)
        """
        #ETAPE 1 : on prepare l'url
        request_url = self.track.announce_url
        request_url += "?"
        request_url += "info_hash=" + self.track.info_hash + "&"
        request_url += "peer_id=" + self.master.id + "&"
        request_url += "port=" + str(self.master.port)
        #Gestion d'evenement
        if event:
            request_url += "&event=" + event
        #ETAPE 2 : recuperation de la reponse
        answer = request.urlopen(request_url).read()
        #Note : answer est envoyée en tant que bytestring parce que Réseau
        answer_dict, _ = bencoding.getDecodedObject( byte_to_ascii(answer) )
        #ETAPE 3 : traitement de la réponse
        if "failure_reason" in answer_dict:
            print("Tracker failed with reason "+answer_dict["failure_reason"])
            return []
        else:
            self.interval = answer_dict["interval"]
            return answer_dict["peers"]
        return [] 


    def connect_to(self, peer):
        """
        Crée une connection sortante vers un nouveau peer

        Paramètre :
            - peer : le peer auquel se connecter
        """
        new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_socket.connect( (peer.ip, peer.port) )
        #Start reading on the socket
        reader = Reader_Thread(t_socket=new_socket, stack=[])
        reader.start()
        #Prepare Handshake
        handshake = self.get_handshake()
        #Send it
        new_socket.send( handshake )
        #Wait for answer
        handshake_successful = self.validate_handshake( peer, reader.stack)
        if handshake_successful :
            connection = Connection_Thread(self.track, self, new_socket, self.master, peer, reader)
            connection.start()
        else :
            new_socket.close()
            self.peer_dict.pop(peer.id, "")
        return


    def receive_connection(self, remote_socket, peer, reader):
        """
        Initialise une connection entrante du coté de ce client

        Paramètres :
            - remote_socket : le socket alloué à cette connection
            - peer : le peer ayant initialisé le contact
            - reader : le thread acceptant les messages du peer

        Note : suppose que le handshake a déjà été effectué avant l'appel
        """
        connection = Connection_Thread(self.track, self, remote_socket, self.master, peer, reader)
        connection.start()

    def get_handshake(self):
        """
        Renvoie le message de handshake de ce client pour le torrent téléchargé par l'instance

        Retour :
            - Une chaine d'octet contenant le handshake
        """
        #Prepare Handshake
        handshake = int_to_byte( len(HANDSHAKE_PROTOCOL_ID) ) + HANDSHAKE_PROTOCOL_ID #Protocol
        handshake += code_int_on_size(0, 8) #Reserved
        handshake += ascii_to_byte( self.track.info_hash ) #info_hash
        handshake += ascii_to_byte( self.master.id ) #peer_id
        return handshake

    def validate_handshake(self, peer, reading_stack):
        """
        Vérifie que le handshake reçu est bien valide

        Paramètres :
            - peer : le peer dont on attend le handshake
            - reading_stack : la liste sur laquelle on peut lire les messages du peer une fois reçus

        Retour :
            - True si le handshake est valide, False sinon

        Note : Cette instance ne verifie le handshake que d'une connection sortante
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
            #info_hash
            if byte_to_ascii( msg[:LEN_SHA256] ) != self.track.info_hash:
                return False
            msg = msg[LEN_SHA256:]
            #peer_id
            #Pour un client -> verification qu'on est connecté a la bonne machine
            if peer.id == byte_to_ascii( msg ):
                return True
        #Defaut : echec
        return False

    def terminate(self):
        """
        Finition propre du thread
        """
        #On eteint les connections restantes
        self.track.notify_exit()
        #On indique au serveur de tracking qu'on ne seed plus
        self.contact_tracker("stopped")
        #Si on a eu le torrent on le decompresse
        if self.seeding :
            converter.detorrentify(self.track.folder, self.track.name, self.track.folder)

    def register_connection(self, connection, peer):
        """
        Enregistre une connection

        Paramètres :
            - connection : la nouvelle connection
            - peer : le peer avec lequel la connection communique
        """
        self.peer_dict[peer.id] = peer
        self.peer_connections[peer.id] = connection
        self.peer_timers[peer.id] = time.time()

    def unregister_connection(self, connection, peer):
        """
        Efface une connection de la liste des connections enregistrées

        Paramètres :
            - connection : la connection venant de s'eteindre
            - peer : le peer avec lequel la connection communiquait
        """
        #S'il s'agissait d'une connection complète, on l'ajoute aux connections finies
        if connection.peer_download.is_complete():
            self.complete_peers.append( peer.id )
        #Dans tous les cas on l'efface
        self.peer_dict.pop(peer.id, "")
        self.peer_connections.pop(peer.id, "")
        self.peer_timers.pop(peer.id, "")

"""

==============================================
                TRACKING
==============================================

"""

"""
=======================
    TORRENT COMPLET
=======================
"""
class Torrent_Local_Track( Download_track, Torrent_track ):
    """
    Suit le telechargement d'un Torrent pour 1 client mais n Connections

    Attributs :
        (Non-hérités)   
        - pieces : liste des piece_manager (chacun suivant la piece ayant un indice égal à son 
            propre indice dans la liste)
        - connections : liste non ordonnée des connections suivant ce torrent
    """
    def __init__(self, folder, torrent_name):
        """
        Constructeur

        Paramètres :
            - folder : le dossier local ou trouver le torrent
            - torrent_name : le nom du torrent
        """
        Torrent_track.__init__(self, folder, torrent_name)
        Download_track.__init__(self, self)
        # On recupere les pièces existantes
        filename_dict = get_pieces_filename_by_hash( self.folder, self.piece_hashes )
        # List des piece manager
        self.pieces = []
        for i in range( len(self.piece_hashes) ):
            #Si la piece est preexistante
            piece = None
            if self.piece_hashes[i] in filename_dict :
                #On recupere la piece
                filename = filename_dict[ self.piece_hashes[i] ]
                piece = Piece_manager( self, self.folder, filename, 
                                        self.piece_hashes[i], self.info["piece length"] )
                #On la note comme complete
                piece.set_complete()
                self.pieces_downloaded[i] = True
            else: 
                #On donne nom à la piece
                filename = "_" + self.name + "_p_" + str(i+1) + PIECE_FILE_EXTENSION
                piece = Piece_manager( self, self.folder, filename, 
                                        self.piece_hashes[i], self.info["piece length"] )
                #Dans le toute on nettoie l'emplacement potentiel de la piece
                if os.path.exists( self.folder + filename ):
                    os.remove( self.folder + filename )
            #Cas limite : derniere piece
            if i == len( self.piece_hashes) - 1:
                piece.length = get_torrent_full_size( self.info) % self.info["piece length"]
            #On ajoute la piece à la liste des pieces
            self.pieces.append( piece )
        #
        self.connections = []

    def register_connection(self, connection):
        """
        Enregistre une connection 

        Paramètre :
            - connection : la nouvelle connection a enregistrer
        """
        if not connection in self.connections :
            self.connections.append( connection )

    def unregister_connection(self, connection):
        """
        Efface une connection de la liste des connections enregistrées

        Paramètre :
            - connection : la connection qui vient de se fermer
        """
        if connection in self.connections :
            self.connections.append( connection )
        

    def notify_completion(self, piece_index):
        """
        Indique aux threads en vie que la piece est complete

        Paramètre :
            - piece_index : la piece qui a été complétée
        """
        for connection in self.connections:
            connection.updates_stack.append( piece_index )

    def notify_exit(self):
        """
        Indique aux threads en vie qu'ils doivent s'arreter
        """
        for connection in self.connections:
            connection.updates_stack.append( "SHUTDOWN" )

"""
==============
    PIECE
==============
"""
class Piece_manager():
    """
    Gere les infos concernant une simple piece locale à travers n Connections

    Attributs :
        - manager : le gestionnaire du torrent complet regroupant toutes les pieces
        - hash : le hash attendu pour la piece UNE FOIS COMPLETE
        - length : la longueur totale de la piece UNE FOIS COMPLETE en bytes
        - folder : le chemin d'acces du dossier contenant la piece (finit par un /)
        - filename : le nom de fichier de la piece
        - write_pos : indice ou ecrire dans la piece (donne aussi la longueur déjà ecrite)
        - lock : verrou sur la piece evitant plusieurs lectures/ecritures simultanées
        - may_write : liste des connections pouvant potentiellement ecrire dans la piece
    """

    def __init__(self, manager, folder, filename, piece_hash, piece_len ):
        """
        Constructeur

        Paramètres :
            - manager : le gestionnaire du torrent complet regroupant toutes les pieces
            - folder : le chemin d'acces du dossier contenant la piece (finit par un /)
            - filename : le nom de fichier de la piece
            - piece_hash : le hash attendu de la piece COMPLETE
            - piece_len : longueur totale de la piece COMPLETE en bytes
        """
        self.manager = manager
        # Meta-Info
        self.hash = piece_hash
        self.length = piece_len
        #Piece file Info
        self.folder = folder
        self.filename = filename
        self.write_pos = 0
        self.complete = False
        # Connection Management
        self.lock = threading.Lock()
        self.may_write = []
        

    def write(self, start_pos, byte, connection_id):
        """
        Ecrit des octets dans la pièce

        Paramètres : 
            - start_pos : l'endroit d'ou l'ecriture est supposée commencer (pour verification)
            - byte : la liste de bytes à ecrire dans la pièce
            - connection_id : le Thread.ident de la connection qui ecrit

        Retour
            - False en cas d'erreur, True si l'ecriture s'est bien passée
        """
        
        #On n'ecrit pas dans une piece qui est finie
        if self.complete : 
            return False
        #On n'ecrit pas si la requete n'est pas coherente avec l'etat de la piece
        if start_pos != self.write_pos :
                return False
        #On essaie de recuperer le verrou
        lock_get = self.lock.acquire(False)
        if lock_get:
            #On dit aux autres connection d'annuler leurs requetes 
            #Elle n'aboutiront de toute façon pas au niveau de l'ecriture
            for connection in self.may_write :
                if not connection.is_alive() :
                    self.may_write.remove( connection )
                elif connection.ident != connection_id :
                    index = self.manager.piece_index( self.hash )
                    connection.cancel_sent_requests( index )
            #On cree le fichier si il n'existe pas
            if not os.path.exists(self.folder + self.filename):
                with io.open(self.folder + self.filename, mode="wb" ) as file:
                    pass
            #On ecrit dans le fichier
            with io.open(self.folder + self.filename, mode="r+b" ) as file:
                file.seek( self.write_pos )
                file.write( byte )
                file.flush()
            #On met à jour la piece
            self.write_pos += len( byte )
            #En cas de finition
            if self.write_pos == self.length:
                #On verifie que la piece est bien telle qu'on la veut
                if self.validate():
                    #Si oui, on notifie le reste du monde
                    index = self.manager.piece_index( self.hash )
                    self.complete = True
                    self.manager.pieces_downloaded[ index ] = True
                    self.manager.notify_completion( index )
                else:
                    #Si non, on la remet à zéro
                    os.remove( self.folder + self.filename)
                    self.write_pos = 0
            #On release le lock
            self.lock.release()
            return True
        else:
            return False

    def read(self, start_pos, length):
        """
        Lit des octets de la pièce

        Paramètres :
            - start_pos : l'endroit d'ou commencer la lecture
            - length : la quantité d'octets à lire

        Return 
            - False en cas d'erreur, un objet Bytes/Bytearray sinon
        """
        #On ne peut lire que ce sur quoi on a ecrit
        if start_pos + length > self.write_pos :
            return False
        #On attend de pouvoir lire
        self.lock.acquire(True)
        try:
            #Initialisation hors du scope pour pouvoir return hors du with
            #Return a l'interieur du with serait dangereux 
            byte = None
            #Lecture du Fichier
            with io.open(self.folder + self.filename, mode="rb" ) as file:
                file.seek(start_pos)
                #byte = ascii_to_byte( file.read(length) )
                byte = file.read(length)
            #On libere le verrou
            self.lock.release()
            if byte is None:
                return False
            return byte
        except IOError as e:
            self.lock.release()
            return False

    def validate(self):
        """
        Verifie si la pièce a bien été complétement téléchargée

        Retour :
            - True si la pièce est complète et telle qu'on l'attendait, False sinon
        """
        #On verifie par le hash si la piece est bonne
        hash_test = False
        self.lock.acquire(True)
        try:
            with io.open(self.folder + self.filename, mode="rb" ) as file:
                digest = toy_digest( file.read() )
                hash_test = ( digest == self.hash )
        except IOError as e:
            self.lock.release()
            return False
        #Si on a la piece correcte
        return hash_test

    def set_complete(self):
        """
        Positionne la pièce comme étant complète et conforme à ce qu'on attendait

        Note : Utilisée seulement à l'initialisation quand on trouve une pièce déjà complète
        """
        self.complete = True
        self.write_pos = self.length