#-*- coding:utf-8 -*-
"""


Note d'implementation pour la recuperation des pieces:
	Cette methode de recuperation des pieces est couteuse en temps (elle necessite une lecture
	supplementaire par piece). 
	Je l'ai choisi parce qu'elle est robuste (sauf collision, seules les piece du torrent
	seront recuperées) et parce qu'elle me permet de ne pas garder toutes les pieces en memoire
	en même temps dans le cas d'un fichier de torrent volumineux (par exemple l'integral des
	films et musique appartenant au domaine public lors d'un archivage).
	Il s'agit donc d'un choix fait lors que je l'ai conçue en faveur de la RAM au detriment du temps
	d'execution
"""
from __future__ import division

from math import ceil

import os


import bencoding

from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION



class Torrent_track():
    """
    Objet Minimal utilisé pour conserver les informations d'un torrent

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
            self.info_hash = toy_digest( coded_info_dict )
        self.complete = 1 #Au moins un peer a recupere le torrent (la seed originale)
        self.peers = 1 #idem 

class Download_track():
    """
	Objet Minimal utilisé pour conserver les informations liées au telechargement d'un torrent

    Attributs :
		- torrent : le torrent en cours de telechargement
		- piece_hashes : liste *ordonnée* des hashes des pieces 
		- pieces_downloaded : liste *ordonnée* de l'etat des pieces
			True si la piece est completement telechargée, False sinon
    """
    
    def __init__(self, torrent):
        """
        """
        self.torrent = torrent
        self.piece_hashes = extract_list_pieces_hash( self.torrent.info["pieces"], LEN_SHA256)
        self.pieces_downloaded = [ False ]*len( self.piece_hashes )
        #

    def piece_index(self, piece_hash ):
        """
        """
        return self.piece_hashes.index( piece_hash )

    def piece_hash(self, piece_index ):
        """
        """
        return self.piece_hashes[ piece_index ]


"""
==================
	FONCTIONS
==================
"""
def extract_list_pieces_hash( pieces_string, hash_length):
	"""
	Extraie la liste des hash dont la chaine prise en entree est la concatenation
	
	Parametres Obligatoires :
		- pieces_string : la concatenation en une seule chaine de tous les hash
		- hash_length : la longueur d'un hash
		
	Retour :
		Une liste dont les elements sont les differents hash de la chaine
		La liste suit l'ordre dans lequel les hash sont concatenés
	"""
	nb_pieces = ceil( len( pieces_string ) / LEN_SHA256  ) #Division de python 3 -> Forcement float
	nb_pieces = int( nb_pieces )
	list_pieces_hash = []
	for i in range( nb_pieces ):
		#Note : cette methode respecte l'ordre de concatenation (permet de savoir l'ordre des pieces)
		list_pieces_hash.append( pieces_string[ i*hash_length : (i+1)*hash_length ] )
	#
	return list_pieces_hash




def get_pieces_filename_by_hash( dir, list_hash ):
	"""
	Recupere toutes les pieces contenues dans la liste de hash prise en entree
	
	Parametres Obligatoires :
		- dir : le dossier ou chercher les pieces
		- list_hash : liste contenant les hash des pieces cherchees
		
	Retour :
		Un dictionnaire dont les clés sont les hash des pieces, et les elements
		le nom des fichiers correspondant aux hash
		
	Hypothese de depart:
	SHA256 est suffisamment robuste pour qu'on ne constate pas de collision
	parmi les fichiers PIECE_FILE_EXTENSION contenu dans source_dir
	"""
	part_by_hash = dict()
	for filename in os.listdir( dir ):
		"""
		Test plus robuste mais moins lisible :
		
		index_PF_ext = filename.find(PIECE_FILE_EXTENSION)
		if ( index_PF_ext > 0 and index_PF_ext == len(filename) - len(PIECE_FILE_EXTENSION) ):
			etc...
			
		Il verifie que PIECE_FILE_EXTENSION est bien l'extension du fichier et pas juste
		une partie de son nom, a la machin.bidule.truc
		En pratique je ne l'ai pas implemente parce que je n'ai pas jugé la securité 
		qu'il apportait suffisamment interessante (ouvrir un fichier de ce genre n'est pas
		nocif en soi si c'est accidentel et un assaillant la contournera facilement) et
		surtout parce qu'il était tres peu probable que le cas limite ainsi couvert se 
		presente
		"""
		if PIECE_FILE_EXTENSION in filename:
			with open( dir + filename, "rb" ) as file:
				#On hash le fichier pour comparer aux hash existants
				file_hash = toy_digest( file.read() )
				#Si il fait partie des fichiers hashé on l'indexe
				if file_hash in list_hash :
					part_by_hash[file_hash] = filename
	#
	return part_by_hash


def get_torrent_full_size( info_dict ):
	"""
	Renvoie la taille complete du torrent en bytes 

	Parametres Obligatoires :
		- info_dict : le dictionnaire d'info du torrent décodé

	Retour :
		- La taille totale du torrent une fois rassemblé sous forme d'entier
	"""
	if "length" in info_dict :
		#Cas 1 : Monofichier
		return info_dict["length"]
	else:
		#Cas 2 : Multifichier
		full_size = 0
		for file_dict in info_dict["files"]:
			full_size += file_dict["length"]
		return full_size