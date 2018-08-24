#-*- coding:utf-8 -*-
"""
IMPORTS COMPATIBLES AVEC PYTHON 3
"""
from __future__ import print_function
from future.standard_library import install_aliases
install_aliases()

import urllib.parse
import urllib.request as request
import urllib.response
import urllib.robotparser
import urllib.error


import bencoding
import toy_utils as utils

def dummy_get_tracker():
    """
    Preparation de la requete
    """
    url = "http://localhost:8082/peers/"
    #Torrent Name
    url += "libs" + "?"
    #Infohash
    with open( "torrent/libs" + utils.TORRENT_FILE_EXTENSION ) as f:
        torrent_dict, _ = bencoding.getDecodedObject( f.read() )
        info_dict = torrent_dict["info"]
        coded_info_dict = bencoding.getEncodedDict( info_dict )
        info_hash = utils.toy_digest( coded_info_dict )
        url += "info_hash=" + info_hash + "&"
    #Peer Id
    url += "peer_id=" + "-TY1000-0001TOYIMP01" + "&" 
    #Port
    url += "port=" + "8082"
    #Event
    """
    url += "&event=started"
    """

    """
    Recuperation de la requete
    """
    answer = request.urlopen(url).read()#Note : Envoyé en tant que bytestring parce que relou
    answer_dict, _ = bencoding.getDecodedObject( answer.decode("ascii") )

    print( answer )
    print( answer[0] )
    print( answer_dict )


if __name__ == '__main__':
    dummy_get_tracker()