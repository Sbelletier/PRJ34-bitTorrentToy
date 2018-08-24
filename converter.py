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

TODO : Detecter a la detorrentification si il manque des pieces et envoyer une erreur
"""
from math import ceil # Arrondi au superieur

import os # Gerer les dossier
import io # Lecture bufferisée de fichier


import bencoding # Implementation du bencode
from toy_utils import LEN_SHA256, toy_digest
from toy_utils import PIECE_FILE_EXTENSION, TORRENT_FILE_EXTENSION


"""
====================
	UTILITAIRES
====================
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


"""
=========================
	TORRENTIFICATION
=========================
"""
def torrentify( source, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	Convertit une source en torrent
	
	Parametres obligatoires:
		- source : le nom du fichier/ la liste des noms des fichiers (chemin d'acces relatif inclu)
			a convertir
		- torrent_name : le nom du torrent a creer
	Parametres optionnels:
		- target_dir : le dossier ou creer le torrent. Sa valeur par defaut est ./torrent/
		- piece_length : la longueur maximum pour une piece, en bits. Sa valeur par defaut est 64 Ko
	
	Note: Le tracker doit modifier le fichier .torrent pour changer l'Annonce
	"""
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#
	if type(source) == str:
		_torrentify_single_file( source, torrent_name, target_dir, piece_length )
	elif type(source) == list:
		_torrentify_multi_files( source, torrent_name, target_dir, piece_length )
	#No return



def _torrentify_single_file( source, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	Convertit un fichier simple en torrent.
	
	Parametres obligatoires:
		- source : le nom du fichier a convertir
		- torrent_name : le nom du torrent a creer
	Parametres optionnels:
		- target_dir : le dossier ou creer le torrent. Sa valeur par defaut est ./torrent/
		- piece_length : la longueur maximum pour une piece, en bits. Sa valeur par defaut est 64 Ko
	
	Note: Le tracker doit modifier le fichier .torrent pour changer l'Annonce
	"""
	#preparation du nom de fichier
	source.replace("\\", "/")
	file_name = ""
	file_path = source.split("/")
	# (On enleve ce qui pourrait etre un disque dur par precaution)
	for dir in file_path:
		if ':' in dir or "." == dir or ".." == dir:
			file_path.remove( dir )
		else:
			file_name += dir 
			if not( dir == file_path[-1] ):
				file_name += "/"
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
			torrent_info_dict["pieces"] += toy_digest( byte_string )
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
def _torrentify_multi_files( sources, torrent_name, target_dir = "./torrent/", piece_length = 1024*64 ):
	"""
	Convertit une source multifichier en torrent
	
	Parametres obligatoires:
		- source : la liste des noms de fichiers (chemin relatif inclu) a convertir
		- torrent_name : le nom du torrent a creer
	Parametres optionnels:
		- target_dir : le dossier ou creer le torrent. Sa valeur par defaut est ./torrent/
		- piece_length : la longueur maximum pour une piece, en bits. Sa valeur par defaut est 64 Ko
	
	Note: Le tracker doit modifier le fichier .torrent pour changer l'Annonce
	"""
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
			if ':' in dir or "." == dir or ".." == dir:
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
					torrent_info_dict["pieces"] += toy_digest( piece_content )
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
		torrent_info_dict["pieces"] += toy_digest( piece_content )
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
def detorrentify( source_dir, torrent_name, target_dir=None ):
	"""
	Convertit un Torrent en sa source d'origine
	
	Parametres Obligatoires :
		- source_dir : le dossier contenant le torrent
		- torrent_name : le nom du torrent
	
	Parametres Optionnels
		- target_dir : le dossier ou extraire le resultat final
			si target_dir n'est pas specifie, le Torrent est extrait dans un
			dossier de nom *torrent_name*
	
	Hypothese de depart: 
	Tous les fichiers PIECE_FILE_EXTENSION appartenant au torrent sont 
	contenus dans source_dir
	"""
	#
	if not target_dir:
		target_dir = torrent_name + "/"
	#Creation du dossier cible
	if not os.path.exists(target_dir[:-1]):
		os.makedirs(target_dir[:-1])
	#Recuperation du dictionnaire du torrent
	torrent_info_dict = dict()
	with open( source_dir + torrent_name + TORRENT_FILE_EXTENSION, "r" ) as file:
		#On sait qu'un fichier torrent contient un dictionnaire, on ne retient donc pas le titre
		torrent_dict, _ = bencoding.getDecodedObject( file.read() )
		torrent_info_dict = torrent_dict["info"]
	#
	if "files" in torrent_info_dict:
		_detorrentify_multi_files( source_dir, torrent_name, torrent_info_dict, target_dir)
	elif "length" in torrent_info_dict:
		_detorrentify_single_file( source_dir, torrent_name, torrent_info_dict, target_dir)
	#No return


	
def _detorrentify_single_file( source_dir, torrent_name, torrent_info_dict, target_dir ):
	"""
	Convertit le Torrent d'un fichier unique en son fichier d'origine
	
	Parametres Obligatoires :
		- source_dir : le dossier contenant le torrent
		- torrent_name : le nom du torrent
		- target_dir : le dossier ou extraire le resultat final
	
	Hypothese de depart: 
	Tous les fichiers PIECE_FILE_EXTENSION appartenant au torrent sont 
	contenus dans source_dir
	"""
	#Recuperation des hash du .TORRENT_FILE_EXTENSION
	list_pieces_sha = extract_list_pieces_hash( torrent_info_dict["pieces"], LEN_SHA256 )
	#Recuperation des hash des .PIECE_FILE_EXTENSION
	part_by_hash = get_pieces_filename_by_hash( source_dir, list_pieces_sha )
	#
	file_path = torrent_info_dict["name"]
	#Reecriture du fichier contenu dans le torrent
	with io.open( target_dir + file_path, "wb" ) as target:
		for hash in list_pieces_sha:
			with open( source_dir + part_by_hash[hash], "rb" ) as piece:
				target.write( piece.read() )
		target.flush()
	#Rien a retourner


	
def _detorrentify_multi_files( source_dir, torrent_name, torrent_info_dict, target_dir ):
	"""
	Convertit un Torrent Multifichiers en ses fichiers d'origine
	
	Parametres Obligatoires :
		- source_dir : le dossier contenant le torrent
		- torrent_name : le nom du torrent
		- target_dir : le dossier ou extraire le resultat final
	
	Hypothese de depart: 
	Tous les fichiers PIECE_FILE_EXTENSION appartenant au torrent sont 
	contenus dans source_dir
	"""
	#Recuperation des hash du .TORRENT_FILE_EXTENSION
	list_pieces_sha = extract_list_pieces_hash( torrent_info_dict["pieces"], LEN_SHA256 )
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
		file_path = target_dir
		for folder in file_info_dict["path"][:-1]:
			#On saute les chemins relatifs
			if folder == "..":
				continue
			else:
				file_path += folder + "/"
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