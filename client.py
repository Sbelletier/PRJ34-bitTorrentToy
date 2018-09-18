
#-*- coding:utf-8 -*-
from __future__ import print_function
"""
Ce module contient le client.
Ce client est :
    - multi-torrent (il peut telecharger plusieurs torrent à la fois)
    - multi-peer (il peut contacter plusieurs peer à la fois, potentiellement 
            le même pour 2 torrent différents)

Note : du fait du GIL (Global Interpreter Lock) : bien que le client puisse avoir
plusieurs dizaines de threads actifs, seul un thread est utilisé par la CPU à un
temps donné

BUG : Actuellement, les Connection_Listener_Thread ne se ferment pas comme attendu
à la fin de l'execution (quand leur socket d'ecoute est fermé). Cela signifie que 
l'execution ne se termine pas automatiquement.    
Il faut terminer l'execution à la main.

---

Utilisation :
python client.py -h : lance le serveur de tracking (important)
python client.py : lance 3 clients qui vont tenter de télécharger un torrent via des informations
    disséminées sur chaque torrent.

(plus d'information dans les procedures d'utilisation)
"""
import socket
import threading
import time

from threading_utils import Connection_Listener_Thread
from torrent_manager import Torrent_Local_Track, Torrenting_thread




class Client():
    """
    Client de base 

    Attributs :
        - ip : l'adresse ip du client
        - port : le port sur lequel le client ecoute
        - id : le peer_id du client
        - torrent_dict : un dictionnaire reliant un info_hash au Torrenting_Thread chargé de 
            télécharger le torrent correspondant à cet info_hash
        - s_server : le socket de server sur lequel le client ecoute les connections entrantes
        - listen_thread : le thread chargé d'ecouter les connections entrantes et de les
            dispatcher aux Torrenting_Thread correspondants
    """
    
    def __init__(self, port, ident, ip=None):
        """
        Constructeur 

        Paramètres Obligatoires :
            - port : <Integer> numero de port sur lequel le client doit ecouter
            - ident : <String> peer_id du client 
        
        Paramètre Optionnel :
            - ip : <String> adresse ip du client, générée automatiquement si non specifiée
        """
        if not ip:
            self.ip = gethostbyname(gethostname())
        else:
            self.ip = ip
        self.port = port
        self.id = ident
        #
        self.torrent_dict = dict()
        self.update_stack = []
        #On setup l'hote
        self.s_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s_server.bind( (self.ip, self.port) )
        self.s_server.listen(10)
        self.listen_thread = Connection_Listener_Thread(self.s_server, self)
        self.listen_thread.start()

    def start_torrent_thread(self, folder, torrent_name):
        """
        Lance le Torrent_Thread pour un torrent spécifié

        Paramètres :
            - folder : le dossier contenant le torrent
            - torrent_name : le nom du torrent
        """
        track = Torrent_Local_Track( folder, torrent_name)
        self.torrent_dict[ track.info_hash ] = Torrenting_thread(self, track)
        self.torrent_dict[ track.info_hash ].start()

    def is_running(self):
        """
        Indique si il y a encore un Torrent_Thread actif pour le client
        (dans le cas contraire le client est considéré inactif)

        Retour : 
            - True si au moins un Torrent_Thread lié au client est encore actif,
                False sinon
        """
        for ident in self.torrent_dict:
            if self.torrent_dict[ident].is_alive():
                return True
        return False

    def terminate(self):
        """
        Arrêt propre (tout du moins en théorie) du client

        BUG : Ne déclenche pas l'arret de self.listen_thread
        """
        #self.s_server.shutdown( socket.SHUT_RDWR )
        self.s_server.close()
        for info_hash in self.torrent_dict:
            self.torrent_dict[info_hash].master_stack.append("SHUTDOWN")




if __name__ == '__main__':
    # Main specific import
    import sys
    #Setup Tracker
    if len(sys.argv)>1 and sys.argv[1] == "-h":
        from tracker import Tracker
        from tracking_server import server
        t = Tracker(ip="localhost", port=8082, id="-TY1000-8082TOYIMP01")
        t.bind_to( server )
        t.seize_torrent( "torrent/", "libs" )
        t.run()
    else :
        #Create Clients
        c1 = Client(port=8011, ident="-TY1000-0001TOYIMP01", ip="127.0.0.1")
        c2 = Client(port=8012, ident="-TY1000-0002TOYIMP01", ip="127.0.0.1")
        c3 = Client(port=8013, ident="-TY1000-0003TOYIMP01", ip="127.0.0.1")
        #Start Client 1
        c1.start_torrent_thread("peer1/", "libs")
        #Start Client 2
        c2.start_torrent_thread("peer2/", "libs")
        #Start Client 3
        c3.start_torrent_thread("peer3/", "libs")
        #
        print( "clients started" )
        running = True
        while running:
            running = c1.is_running() or c2.is_running() or c3.is_running()
            print("waiting...")
            time.sleep(3)
        print( "clients done" )
        #Finition
        c1.terminate()
        c2.terminate()
        c3.terminate()
        #Les Connections refusent de se fermer bien qu'il n'y ait plus de socket sur lequel ecouter
        print (threading.enumerate())
        #Bien que les sockets aient été fermées
        


        








