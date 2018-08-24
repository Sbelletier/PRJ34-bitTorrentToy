#-*- coding:utf-8 -*-
"""
Ce fichier contient les classes utilisés pour maintenir un tracker
"""
from libs.bottle import run as bottle_run



import bencoding



from tracking_server import server

from toyUtils import  PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
from toyUtils import LEN_SHA256, toy_hash
from toyUtils import TRACKER_INTERVAL

"""
========================
        TRACKER
=======================
"""

class Tracker( object ):
    """
    Cette classe s'occupe des taches de fond du Tracker. 
    Il inclut un server definit dans le fichier tracking_server.py

    Attributs :
        - id : <String> peer_id du tracker
        - port : <int> port de connection du serveur de tracking
        - ip : <String> adresse du serveur de tracking telle que publiée
        - server : <Instance bottle.Bottle> serveur auquel le tracker est lié
        - interval : <int> Intervalle en seconde entre deux appel pour un peer donné
        - registered_torrents : <dict> Dictionnaire contenant les torrents gérés par le tracker
            - clé -> <String> info_hash du Torrent
            - valeur -> <Instance Torrent_track> resumé du Torrent
        - registered_peers : <dict> Dictionnaire contenant les peer actifs pour un torrent
            - clé -> <String> info_hash du Torrent
            - valeur -> <List<String>> peer_id des torrents pouvant potentiellement transmettre une piece
                du torrent
        - peers_url : <dict> Dictionnaire contenant les adresses des peer
            - clé -> <String> peer_id du peer
            - valeur -> <String> adresse du peer sous la forme "ip:port"
    """
    

    def __init__(self, ip, port, id):
        """
        Constructeur

        Paramètres :
            - ip : adresse IP du tracker -> String
            - port : port du tracker -> int
            - id : peer_id du tracker -> String
        """
        self.registered_torrents = dict()
        self.registered_peers = dict()
        self.peers_url = dict()
        #
        self.ip = ip
        self.port = port
        self.server = None
        self.id = id
        #
        self.interval = TRACKER_INTERVAL

    def seize_torrent(self, torrent_name, folder):
        """
        Modifie le fichier de torrent et le tracker pour qu'il puisse maintenant
        tracker le torrent

        Parametres :
            - torrent_name : le nom du torrent
            - folder : url du dossier local ou trouver le torrent

        Note : Il parait interessant que le tracker ait au moins une version complete du
        Torrent avant de le gerer/de le publier afin qu'il soit capable de l'annoncer
        """
        torrent = Torrent_track( folder, torrent_name)
        self.registered_torrents[torrent.info_hash] = torrent
        self.registered_peers[ torrent.info_hash ] =  [self.id]
        self_url = self.ip + ":" + str(self.port)
        self.peers_url[ self.id ] = self_url
        torrent_dict = dict()
        #MISE A JOUR DE L'ANNONCE DANS LE TORRENT
        with open( folder + torrent_name + TORRENT_FILE_EXTENSION ) as file:
            torrent_dict, _ = bencoding.getDecodedObject( file.read() )
        if len( torrent_dict.keys() ) > 0:
            torrent_dict["announce"] = self_url + "/peers/" + torrent_name
            with open( folder + torrent_name + TORRENT_FILE_EXTENSION, "w" ) as file:
                file.write( bencoding.getEncodedObject(torrent_dict) )
    
    def bind_to( self, instance ):
        """
        Relie le tracker à une instance de serveur locale

        Paramètres :
            - instance : <Instance bottle.Bottle> le serveur à relier

        Note :
        On considere comme bonne pratique dans cette application que le run se fasse coté
        tracker, cad que l'on relie une instance qui n'est pas encore lancée
        """
        instance.tracker = self
        self.server = instance

    def run(self):
        """
        Initialise et lance le serveur de tracking
        """
        bottle_run( self.server, ip = self.ip, port= self.port)


class Torrent_track( object ):
    """
    Objet utilisé pour conserver les informations d'un torrent

    Attributs :
        - folder : <String> Url du dossier local ou trouver le torrent
        - name : <String> Nom du torrent
        - info : <dict> infodict du torrent (voire specification BitTorrent)
        - info_hash : <String> hash du infodict permettant d'authentifier le torrent
        - complete : <Int> nombre de peers ayant telechargé l'intégralité du torrent
        - peers : <Int> nombre de peers actifs pouvant potentiellement seeder le torrent
    """

    def __init__(self, folder, name):
        """
        Constructeur

        Paramètres : 
            - torrent_name : le nom du torrent
            - folder : url du dossier local ou trouver le torrent        
        """
        self.folder = folder
        self.name = name
        with open( folder + name + TORRENT_FILE_EXTENSION ) as file:
            torrent_dict, _ = bencoding.getDecodedObject( file.read() )
            self.info = torrent_dict["info"]
            coded_info_dict = bencoding.getEncodedDict( self.info )
            self.info_hash = toy_hash( coded_info_dict ).hexdigest()
        self.complete = 1 #Au moins un peer a recupere le torrent (la seed originale)
        self.peers = 1 #idem 

        
"""
Main de Test
"""
if __name__ == '__main__':
    t = Tracker(ip="localhost", port=8082, id="-TY1000-8082TOYIMP01")#Azureus style ID
    t.bind_to( server )
    t.seize_torrent( "libs", "torrent/" )
    t.run()