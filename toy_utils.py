#-*- coding:utf-8 -*-
"""
Fichier contenant divers objets/fonctions utiles pour l'application

Note: j'ai choisi SHA256 plutot que SHA1 parce que la norme la plus recente de BitTorrent
(v2 http://www.bittorrent.org/beps/bep_0052.html) a abandonné SHA1 pour SHA256

Note 2: en theorie, je devrais utiliser la methode digest plutot que hexdigest, mais j'ai 
rencontré des problemes d'encodage qui m'ont paru avoir peu a voir avec le sujet.
J'ai donc choisi d'utiliser hexdigest pour esquiver le probleme
"""
from sys import version_info

import hashlib # Hash SHA256 
import random # Random id generation

"""
===================
	CONSTANTES
===================
"""
LEN_SHA256 = 64 #Longueur d'un hash par definition de SHA256 (x2 car on utilise hexdigest). 
#Il est cependant possible de tester avec LEN_SHA256 = len( hashlib.sha256("").hexdigest() )
PIECE_FILE_EXTENSION = ".bpart"
TORRENT_FILE_EXTENSION = ".torrent"
LOG_FILE_EXTENSION = ".log"


TRACKER_INTERVAL = 5

LEN_STRING_ID = 20
"""
==================
	INSTANCES
==================
"""

toy_hash = hashlib.sha256 #On definit le hash qu'on utilise comme SHA256

"""
==================
	FONCTIONS
==================
"""
def toy_digest( a_string ):
	"""
	Renvoie le hash standard de l'application pour une chaine

	Paramètre :
		- a_string : Chaine dont on veut le hash
	
	Retour :
		Le hash utilisé au sein de l'application pour cette chaine
	"""
	return toy_hash( a_string ).hexdigest()

def random_peer_id():
	"""
	"""
	prefix = "-TY1000-" #Préfixe façon Azureus
	suffix = "TOYIMP" #Suffixe non présent dans la norme Azureus pour distinguer d'un vrai client
	len_id = LEN_STRING_ID - len(prefix) - len(suffix)
	#Generation de l'id aléatoire
	rand_id = str( random.randint(0, (10**len_id) -1 ) )
	#Ajout de 0 pour remplir la taille de chaine necessaire
	while( len(rand_id) < len_id ):
		rand_id = "0" + rand_id
	#
	return prefix + rand_id + suffix

def byte_to_ascii( byte ):
	"""
	"""
	return byte.decode("ascii")

def ascii_to_byte( string ):
	"""
	"""
	if version_info < (3, 0):
		return bytearray(string, "ascii")
	else:
		return bytes( string, "ascii" )

def byte_to_int( byte ):
	"""
	"""
	bstring = ascii_to_byte( byte )
	bstring.reverse()
	val = 0
	for i in range( len( bstring ) ):
		val += bstring[i] * (256**i)
	return val

def int_to_byte( integer ):
	"""
	breaks down in byte-size seq
	"""
	seq = []
	while integer > 0:
		seq.insert( 0, integer % 256 )
		integer = int( integer // 256 )
	#Cas limite integer == 0
	if seq == []:
		seq = [0]
	#
	if version_info < (3, 0):
		return bytearray(seq )
	else:
		return bytes( seq )