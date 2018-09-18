# PRJ 34 Procédures

**NB** : ce programme n'a été  testé qu'avec python 2.7 et n'a aucune garantie de fonctionner 
avec python 3.

**NB2** : bottle.py est une dépendance externe que je n'ai pas ecrite.

## Démonstration principale

1. Ouvrir les dossiers _peer1_ , _peer2_ et _peer3_. Y supprimer le dossier _libs_, et les fichiers
 `_libs_p_X.bpart` ( `X` est un nombre). Ces fichiers sont les fichiers générés par la communication
entre les pairs.
2. Ouvrir le dossier du projet dans deux consoles **A** et **B**
3. Dans **A**, envoyer la commande `python client.py -h` pour lancer le traqueur.
4. (_Facultatif_) copier le fichier `libs.torrent` du dossier _torrent_ dans les trois dossier
 _peer_
pour garantir que les clients se connectent bien au bon tracker.
5. Dans **B**, envoyer la commande `python client.py` pour lancer les trois connections.
6. Observer les fichiers de pièces qui se construisent et le dossier lib crée lors de 
l'extraction finale.
7. Quand la console **B** affiche une liste de Thread arrêter manuellement son processus. Le serveur
bottle dans la console **A** pourra être arrêté d'un simple ctrl+c.

## Demonstration de la communication 1 pair vers 2 pairs (pas de choking)

1. Ouvrir les dossiers _peer1_ , _peer2_ et _peer3_. Y supprimer les fichiers `_libs_p_X.bpart`
 ( `X` est un nombre). Ces fichiers sont les fichiers générés par la communication entre les pairs.
2. Ouvrir le dossier du projet dans une console **A**
3. Dans **A**, envoyer la commande `python dummy_wire.py -m` pour ouvrir les 3 connections.
4. Observer les traces, qui donnent les requêtes reçues et les blocks envoyés par le pair 1, qui
 communique avec le pair 2 et avec le pair 3. Voir aussi les fichiers se construire progressivement.
 
 ## Demonstration de la communication entre 2 pairs (pas de choking)
 
1. Ouvrir les dossiers _peer1_ et _peer2_. Y supprimer les fichiers `_libs_p_X.bpart` ( `X` est 
un nombre). Ces fichiers sont les fichiers générés par la communication entre les pairs.
2. Ouvrir le dossier du projet dans deux consoles **A** et **B**
3. Dans **A**, envoyer la commande `python dummy_wire.py -h` pour ouvrir l'hôte.
4. Dans **B**, envoyer la commande `python dummy_wire.py` pour connecter le client.
5. Observer les traces, qui donnent les requêtes reçues et les blocks envoyés par chaque pair.
 Voir aussi les fichiers se construire progressivement.
 
 ## Démonstration des capacités du traqueur
 
1. Ouvrir le dossier du projet dans deux consoles **A** et **B**
2. Dans **A**, envoyer la commande `python tracker.py` pour lancer le traqueur.
3. Dans **B**, envoyer la commande `python dummy_request.py` pour envoyer une requête de test.
4. Observer les traces.

