#-*- coding:utf-8 -*-
"""
"""

import threading
import os # Gerer les dossier
import io # Lecture bufferisée de fichier

from torrent_utils import Torrent_track, Download_track
from torrent_utils import get_pieces_filename_by_hash, get_torrent_full_size
from toy_utils import byte_to_ascii, ascii_to_byte
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION

class Torrent_manager( Download_track, Torrent_track ):
    """
    Gere le telechargement d'un Torrent pour 1 client mais n Connections
    """
    def __init__(self, folder, torrent_name):
        Torrent_track.__init__(self, folder, torrent_name)
        Download_track.__init__(self, self)
        # Get the existing pieces
        filename_dict = get_pieces_filename_by_hash( self.folder, self.piece_hashes )
        # Piece List
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
        """
        if not connection in self.connections :
            self.connections.append( connection )

    def unregister_connection(self, connection):
        """
        """
        if connection in self.connections :
            self.connections.append( connection )
        

    def notify_completion(self, piece_index):
        """
        Indique aux threads en vie que la piece est complete
        """
        for connection in self.connections:
            connection.updates_stack.append( piece_index )

    def notify_exit(self):
        """
        Indique aux threads en vie qu'ils doivent s'arreter
        """
        for connection in self.connections:
            connection.updates_stack.append( "SHUTDOWN" )


class Piece_manager():
    """
    Gere les infos concernant une simple piece à travers n Connections
    """
    def __init__(self, manager, folder, filename, piece_hash, piece_len ):
        """
        hash est le hash attendu de la piece COMPLETE
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
                    connection.cancel_requests( index )
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
        """
        #On verifie par le hash si la piece est bonne
        hash_test = False
        with io.open(self.folder + self.filename, mode="rb" ) as file:
            digest = toy_digest( file.read() )
            hash_test = ( digest == self.hash )
        #Si on a la piece correcte
        return hash_test

    def set_complete(self):
        """
        A UTILISER SEULEMENT A L'INITIALISATION QUAND ON TOMBE SUR UNE PIECE DEJA COMPLETE
        """
        self.complete = True
        self.write_pos = self.length