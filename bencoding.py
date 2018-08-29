#-*- coding:utf-8 -*-
"""
Ce fichier contient les fonctions utilitaires
pour gerer l'encodage bencoding
"""
from __future__ import print_function


def getDecodedInt( string ):
    """
    Renvoie l'entier dont l'encodage commence a string[0],
    et une version modifiée de string d'ou l'encodage de
    l'entier lu a été consommé

    Hypothèse de départ :
    string[0] == 'i'
    """
    string = string[1:] #On enleve le premier i
    intString = ""#Chaine contenant l'entier en lui même
    #Lecture de l'entier
    while( string[0] != 'e'):
        intString += string[0]
        string = string[1:]
    #Conversion
    integer = int( intString )
    #Retour
    string = string[1:] #on enleve le e final
    return integer, string


def getEncodedInt( integer ):
    """
    Renvoie la chaine encodant l'entier pris en parametre
    """
    return "i" + str( integer ) + "e"



def getDecodedString( string ):
	"""
	Renvoie la chaine de caracteres dont l'encodage commence a string[0],
	et une version modifiée de string d'ou l'encodage de la chaine lue
	a été consommé
	
	Hypothèse de départ :
	string[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')
	"""
	lBuffer = ""
    #Lecture de la longueur
	while( string[0] != ':'):
		lBuffer += string[0]
		string = string[1:]
	string = string[1:] #On retire le : de separation
    #Conversion de la longueur
	stringLength = int( lBuffer )
    #Lecture du contenu de la chaine
	returnString = string[:stringLength]
	#Extraction du contenu de la chaine du bencode original
	string = string[stringLength:]
	#Retour
	return returnString, string


def getEncodedString( string ):
    """
    Renvoie la chaine encodant la chaine prise en paramètre
    """
    return str( len( string ) ) + ":" + string




def getDecodedList( string ):
    """
    Renvoie la liste dont l'encodage commence a string[0],
    et une version modifiée de string d'ou l'encodage de 
    la liste lue a été consommé

    Hypothèse de départ :
    string[0] == 'l'
    """
    string = string[1:]#On enleve le l initial
    bencodedList = []
    #Lecture de la liste
    while( string[0] != 'e' ):
        content = None
        #Switch sur les 4 elements possibles
        if( string[0] == 'l' ):
            content, string = getDecodedList( string )
        elif( string[0] == 'd' ):
            content, string = getDecodedDict( string )
        elif( string[0] == 'i'):
            content, string = getDecodedInt( string )
        elif( string[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') ):
            content, string = getDecodedString( string )
        #On append le nouveau contenu
        bencodedList.append(content)
    #Retour
    string = string[1:] #On enleve le e final
    return bencodedList, string


def getEncodedList( listInput ):
    """
    Renvoie la chaine encodant la liste prise en paramètre
    """
    string = "l"
    for element in listInput:
        string += getEncodedObject(element)
    string += "e"
    return string



def getDecodedDict( string ):
    """
    Renvoie le dictionnaire dont l'encodage commence a string[0],
    et une version modifiée de dictionnaire d'ou l'encodage du 
    dictionnaire lue a été consommé

    Hypothèse de départ :
    string[0] == 'd'
    """
    string = string[1:]#On enleve le l initial
    bencodedDict = dict()
    while( string[0] != 'e' ):
        #On lit la clé
        key, string = getDecodedString( string )
        #On lit l'element indexé
        content = None
        #Switch sur les 4 elements possibles
        if( string[0] == 'l' ):
            content, string = getDecodedList( string )
        elif( string[0] == 'd' ):
            content, string = getDecodedDict( string )
        elif( string[0] == 'i'):
            content, string = getDecodedInt( string )
        elif( string[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') ):
            content, string = getDecodedString( string )
        #On append le nouveau contenu
        bencodedDict[key] = content
    #Retour
    string = string[1:] #On enleve le e final
    return bencodedDict, string


def getEncodedDict( dico ):
    """
    Renvoie la chaine encodant le dictionnaire pris en paramètre
    """
    string = "d"
    keys = dico.keys()
    keys.sort()
    for key in keys:
        string += getEncodedString(key)
        string += getEncodedObject( dico[key] )
    string += "e"
    return string



def getDecodedObject( string ):
    """
    Renvoie l'element encodé et son type en tant que string

    Renvoie None, "error" en cas d'erreur de lecture
    """
    #Switch sur les 4 elements possibles
    if( string[0] == 'l' ):
        content, string = getDecodedList( string )
        return content, "list"
    elif( string[0] == 'd' ):
        content, string = getDecodedDict( string )
        return content, "dict"
    elif( string[0] == 'i'):
        content, string = getDecodedInt( string )
        return content, "int"
    elif( string[0] in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9') ):
        content, string = getDecodedString( string )
        return content, "str"
    return None, "error"


def getEncodedObject( obj ):
    """
    Renvoie la version encodee de l'objet pris en entree
    """
    if type( obj ) == int:
        return getEncodedInt( obj )
    elif type( obj ) == str:
        return getEncodedString( obj )
    elif type( obj ) == list:
        return getEncodedList( obj )
    elif type( obj ) == dict:
        return getEncodedDict( obj )
    else:
        return getEncodedString( str(obj) )



"""
Petit Test:
Encodage de "ll12:constitutioni35ee10:sauvegardei9ed3:bar4:spam3:fooi42eee"
Retour Attendu : "[ 
                    [ 'constitution', 35 ], 
                    'sauvegarde', 
                    9, 
                    {'foo':42, 'bar':'spam'}    
                ]"
"""
if __name__ == '__main__':
    string = "ll12:constitutioni35ee10:sauvegardei9ed3:bar4:spam3:fooi42eee"
    print( "initial bencoding")
    print( string)
    print( "decoding")
    result, typeObject = getDecodedObject( string )
    print( result)
    print( typeObject)
    print( "reencoding")
    print( getEncodedObject( result ))
    