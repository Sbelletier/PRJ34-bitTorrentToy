#-*- coding:utf-8 -*-

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