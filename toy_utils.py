#-*- coding:utf-8 -*-
"""
Fichier contenant divers objets/fonctions utiles pour l'application

Note: j'ai choisi SHA256 plutot que SHA1 parce que la norme la plus recente de BitTorrent
(v2 http://www.bittorrent.org/beps/bep_0052.html) a abandonné SHA1 pour SHA256

Note 2: en theorie, je devrais utiliser la methode digest plutot que hexdigest, mais j'ai 
rencontré des problemes d'encodage qui m'ont paru avoir peu a voir avec le sujet.
J'ai donc choisi d'utiliser hexdigest pour esquiver le probleme
"""
import hashlib # Hash SHA256 

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