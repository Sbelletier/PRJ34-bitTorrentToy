#-*- coding:utf-8 -*-
"""
Ce fichier contient la partie web-server du tracker
"""
from libs.bottle import route, Bottle, request



from toyUtils import LEN_SHA256, toy_hash
from toyUtils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION
import bencoding

"""
===========================
    SERVEUR DE TRACKING
===========================
"""

server = Bottle()
server.tracker = None #Object of class Tracker from tracker

"""
route de test : verifie que le serveur est en ligne
"""
@server.route('/')
def hello():
    return "Welcome to " + server.tracker.id

"""
route principale : renvoie les peers enregistré par le tracker
"""
@server.route('/peers/<torrent_name>', method='GET')
def serve_torrent_info( torrent_name ):
    #Preparation de la réponse serveur
    answer = dict()
    #Recuperation de l'info_hash
    info_hash =  request.query.info_hash
    #On se simplifie la vie
    torrents = server.tracker.registered_torrents
    peers = server.tracker.registered_peers
    peers_url = server.tracker.peers_url
    #On verifie que le info_hash existe
    if info_hash in torrents :
        torrent_track = torrents[info_hash]
        #On verifie que c'est le info_hash idoine
        if torrent_name == torrent_track.name :
            #On recupere les infos du client
            client_id = request.query.peer_id
            client_port = request.query.port
            #
            client_url = request.remote_addr + ":" + client_port
            """
            Gestion des evenements
            """
            if "event" in request.query:
                event = request.query.event
                if event == "started":
                    torrent_track.peers += 1
                    peers[ info_hash ].append( client_id )
                    peers_url[ client_id ] = client_url
                elif event == "stopped":
                    torrent_track.peers -= 1
                    peers[ info_hash ].remove( client_id )
                elif event == "completed":
                    torrent_track.complete += 1
            """
            Preparation de la réponse
            """
            answer["interval"] = server.tracker.interval
            answer["peers"] = []
            #Dictionnaire de peer
            for peer_id in peers[info_hash]:
                url = peers_url[peer_id]
                idx = url.find(":")
                ip = url[:idx]
                port = url[idx+1:]
                answer["peers"].append( {"peer_id":peer_id, "ip":ip, "port":port} )
        #Cas d'erreur  
        else:
            answer["failure_reason"] = "Wrong info_hash for torrent " + torrent_name + "."
    else:
        answer["failure_reason"] = "Wrong info_hash for torrent " + torrent_name + "."
    return bencoding.getEncodedDict( answer )
