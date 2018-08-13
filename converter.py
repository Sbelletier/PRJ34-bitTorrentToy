#-*- coding:utf-8 -*-
"""
Ce fichier sert a convertir un fichier/un groupe de fichier
en fragments de fichier pour servir de torrent


Note d'implementation pour la recuperation des pieces:
	Cette methode de recuperation des pieces est couteuse en temps (elle necessite une lecture
	supplementaire par piece). 
	Je l'ai choisi parce qu'elle est robuste (sauf collision, seules les piece du torrent
	seront recuperées) et parce qu'elle me permet de ne pas garder toutes les pieces en memoire
	en même temps dans le cas d'un fichier de torrent volumineux (par exemple l'integral des
	films et musique appartenant au domaine public lors d'un archivage).
	Il s'agit donc d'un choix fait lors que je l'ai conçue en faveur de la RAM au detriment du temps
	d'execution

Note: j'ai choisi SHA256 plutot que SHA1 parce que la norme la plus recente de BitTorrent
(v2 http://www.bittorrent.org/beps/bep_0052.html) a abandonné SHA1 pour SHA256

Note 2: en theorie, je devrais utiliser la methode digest plutot que hexdigest, mais j'ai 
rencontré des problemes d'encodage qui m'ont paru avoir peu a voir avec le sujet.
J'ai donc choisi d'utiliser hexdigest pour esquiver le probleme

TODO : Detecter a la detorrentification si il manque des pieces et envoyer une erreur
"""
from math import ceil # Arrondi au superieur

import os # Gerer les dossier
import io # Lecture bufferisée de fichier
import hashlib # Hash SHA256 

import bencoding # Implementation du bencode

"""
===================
	CONSTANTES
===================
"""
LEN_SHA256 = 64 #Longueur d'un hash par definition de SHA256 (x2 car on utilise hexdigest). 
#Il est cependant possible de tester avec LEN_SHA256 = len( hashlib.sha256("").hexdigest() )
PIECE_FILE_EXTENSION = ".bpart"
TORRENT_FILE_EXTENSION = ".torrent"


"""
====================
	UTILITAIRES
====================
"""
def extract_list_pieces_hash( pieces_string ):
	"""
	"""
	hash_length = LEN_SHA256
	nb_pieces = ceil( len( pieces_string ) / float( LEN_SHA256 ) ) #On evite un resultat tronque
	nb_pieces = int( nb_pieces )
	list_pieces_hash = []
	for i in range( nb_pieces ):
		#Note : cette methode respecte l'ordre de concatenation (permet de savoir l'ordre des pieces)
		list_pieces_hash.append( pieces_string[ i*hash_length : (i+1)*hash_length ] )
	#
	return list_pieces_hash
	
	
def get_pieces_filename_by_hash( dir, list_hash ):
	"""
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
				file_hash = hashlib.sha256( file.read() ).hexdigest()
				#Si il fait partie des fichiers hashé on l'indexe
				if file_hash in list_hash :
					part_by_hash[file_hash] = filename
	#
	return part_by_hash


"""
=========================
	TORRENTIFICATION
=========================
"""
def torrentify( source, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	
	"""
	if type(source) == str:
		torrentify_single_file( source, torrent_name, target_dir, piece_length )
	elif type(source) == list:
		torrentify_multi_files( source, torrent_name, target_dir, piece_length )
	#No return



def torrentify_single_file( source, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	Convertit un fichier simple en torrent.
	
	Parametres obligatoires:
		- source : le nom du fichier
		- torrent_name : le nom du torrent a creer
	Parametres optionnels:
		- target_dir : le dossier ou creer le torrent
		- piece_length : longueur de chaque piece contenant
	
	Note: Le tracker doit modifier le fichier .torrent pour changer l'Annonce
	"""
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#Preparation des infos du torrent
	torrent_info_dict = { "piece length":piece_length, "pieces":"", "name":source, "length":0 }
	piece_no = 1
	#Ouverture du fichier a convertir
	with io.open( source, mode="rb") as f:
		#Copie piece par piece
		byte_string = f.read(piece_length)
		while byte_string != "":
			#On ouvre le fichier de piece
			current_piece = open( target_dir + "_" + torrent_name + "_piece_" + str(piece_no) + PIECE_FILE_EXTENSION, mode="wb" )
			#On copie le contenu
			current_piece.write( byte_string )
			#Hash du contenu de la piece
			torrent_info_dict["pieces"] += hashlib.sha256( byte_string ).hexdigest()
			#Mise a jour de la longueur du fichier
			torrent_info_dict["length"] += len( byte_string )
			#Fermeture du fichier
			current_piece.close()
			#Preparation de la piece suivante
			piece_no += 1
			byte_string = f.read( piece_length )
	#Preparation du dictionnaire final du torrent
	torrent_dict = { "announce":"", "info":torrent_info_dict }
	#
	with open( target_dir + torrent_name + TORRENT_FILE_EXTENSION , "w" ) as f:
		f.write( bencoding.getEncodedObject( torrent_dict ) )
	#Pas de retour necessaire


	
#NOTE POUR LE FUTUR : N'accepter que les paths relatifs
def torrentify_multi_files( sources, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	
	"""
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#Preparation des infos du torrent
	torrent_info_dict = { "piece length":piece_length, "pieces":"", "name":torrent_name, "files":[] }
	#Information necessaires a l'ecriture des pieces
	piece_no = 1
	piece_content = ""
	#On ouvre la premiere piece
	current_piece = open( target_dir + "_" + torrent_name + "_piece_" + str(piece_no) + PIECE_FILE_EXTENSION, mode="wb" )
	#On boucle sur chaque fichier source
	for source in sources:
		#Creation du dictionnaire pour le fichier
		source.replace("\\", "/")
		file_path = source.split("/")
		# (On enleve ce qui pourrait etre un disque dur par precaution)
		for dir in file_path:
			if ':' in dir:
				file_path.remove( dir )
		file_info_dict = {"path":file_path, "length":0}
		#Ouverture du fichier a convertir
		with io.open( source, mode="rb") as f:
			#Copie piece par piece
			byte_string = f.read( piece_length - len( piece_content ) )
			while byte_string != "" :
				#Si on cree une nouvelle piece, on l'ouvre (le test est placé ici pour ne pas ouvrir de piece excessive)
				if piece_content == "":
					current_piece = open( target_dir + "_" + torrent_name + "_piece_" + str(piece_no) + PIECE_FILE_EXTENSION, mode="wb" )
				#On ecrit dans le fichier
				current_piece.write( byte_string )
				#Preparation 
				piece_content += byte_string
				#Si la piece actuelle est complete 
				if len( piece_content ) == piece_length:
					current_piece.close()
					torrent_info_dict["pieces"] += hashlib.sha256( piece_content ).hexdigest()
					#Remise a zero pour la prochaine piece
					piece_no += 1
					piece_content = ""
				#Maj du dictionnaire du fichier
				file_info_dict["length"] += len( byte_string )
				#Lecture du bout suivant du fichier
				byte_string = f.read( piece_length - len( piece_content ) )
		torrent_info_dict["files"].append( file_info_dict )
	#On ferme la derniere piece
	if not current_piece.closed:
		torrent_info_dict["pieces"] += hashlib.sha256( piece_content ).hexdigest()
		current_piece.close() 
	#Preparation du dictionnaire final du torrent
	torrent_dict = { "announce":"", "info":torrent_info_dict }
	#
	with open( target_dir + torrent_name + TORRENT_FILE_EXTENSION , "w" ) as f:
		f.write( bencoding.getEncodedObject( torrent_dict ) )
	#Pas de retour necessaire
	
"""
===========================
	DETORRENTIFICATION
===========================
"""
def detorrentify_single_file( source_dir, torrent_name, target_dir ):
	"""
	
	Hypotheses de depart: 
	Tous les fichiers PIECE_FILE_EXTENSION appartenant au torrent sont 
	contenus dans source_dir
	SHA256 est suffisamment robuste pour qu'on ne constate pas de collision
	parmi les fichiers PIECE_FILE_EXTENSION contenu dans source_dir
	
	"""
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#Recuperation du dictionnaire du torrent
	torrent_info_dict = dict()
	with open( source_dir + torrent_name + TORRENT_FILE_EXTENSION, "r" ) as file:
		#On sait qu'un fichier torrent contient un dictionnaire
		torrent_info_dict = bencoding.getDecodedObject( file.read() )[0]["info"]
	#Recuperation des hash du .TORRENT_FILE_EXTENSION
	list_pieces_sha = extract_list_pieces_hash( torrent_info_dict["pieces"] )
	#Recuperation des hash des .PIECE_FILE_EXTENSION
	part_by_hash = get_pieces_filename_by_hash( source_dir, list_pieces_sha )
	#Reecriture du fichier contenu dans le torrent
	with io.open( target_dir + torrent_info_dict["name"], "wb" ) as target:
		for hash in list_pieces_sha:
			with open( source_dir + part_by_hash[hash], "rb" ) as piece:
				target.write( piece.read() )
		target.flush()
	#Rien a retourner


	
def detorrentify_multi_files( source_dir, torrent_name, target_dir ):
	"""
	
	Hypotheses de depart: 
	Tous les fichiers PIECE_FILE_EXTENSION appartenant au torrent sont 
	contenus dans source_dir
	SHA256 est suffisamment robuste pour qu'on ne constate pas de collision
	parmi les fichiers PIECE_FILE_EXTENSION contenu dans source_dir
	
	"""
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#Recuperation du dictionnaire du torrent
	torrent_info_dict = dict()
	with open( source_dir + torrent_name + TORRENT_FILE_EXTENSION, "r" ) as file:
		#On sait qu'un fichier torrent contient un dictionnaire
		torrent_info_dict = bencoding.getDecodedObject( file.read() )[0]["info"]
	#Recuperation des hash du .TORRENT_FILE_EXTENSION
	list_pieces_sha = extract_list_pieces_hash( torrent_info_dict["pieces"] )
	#Recuperation des hash des .PIECE_FILE_EXTENSION
	part_by_hash = get_pieces_filename_by_hash( source_dir, list_pieces_sha )
	"""
	Reecriture des fichiers
	"""
	file_info_list = torrent_info_dict["files"]
	#Information necessaires a la lecture des pieces
	piece_length = torrent_info_dict["piece length"]
	piece_idx = 0
	#On ouvre la premiere piece
	current_piece = open( source_dir + part_by_hash[ list_pieces_sha[piece_idx] ], mode="rb" )
	#Iteration sur tous les fichiers
	for file_info_dict in file_info_list:
		#On prepare d abord le dossier d'arrivee
		file_path = target_dir+"/"
		for dir in file_info_dict["path"][:-1]:
			file_path += dir + "/"
		if not os.path.exists(file_path):
			os.makedirs( file_path[:-1] )
		#Recuperation du nom complet du fichier
		file_path += file_info_dict["path"][-1]
		#
		remaining_bytes = file_info_dict["length"]
		with io.open( file_path, "wb" ) as target:
			while remaining_bytes > 0:
				#On lit au maximum piece_length pour eviter de detruire la memoire
				byte_string = current_piece.read( min( piece_length, remaining_bytes ) )
				#Si on a lu l'entiereté de la piece actuelle
				while byte_string == "":
					#On ferme la piece
					current_piece.close()
					#On ouvre la suivante
					piece_idx += 1
					current_piece = open( source_dir + part_by_hash[ list_pieces_sha[piece_idx] ], mode="rb" )
					#On la lit
					byte_string = current_piece.read( min( piece_length, remaining_bytes ) )
				#On copie dans le fichier de sortie
				target.write( byte_string )
				remaining_bytes -= len( byte_string )
			target.flush()
	#On ferme la derniere piece
	if not current_piece.closed:
		current_piece.close() 
	#Rien a retourner
#	