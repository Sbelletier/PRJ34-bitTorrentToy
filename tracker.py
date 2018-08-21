from libs import bottle


server = bottle.Bottle()
@server.route('/')
def hello():
    return "Welcome to " + server.tracker.name


class Tracker( object ):
    server = bottle.Bottle()

    def __init__(self):
        self.name = "Tracker"
    
    
        



if __name__ == '__main__':
    t = Tracker()
    server.tracker = t
    bottle.run( server, host="localhost", port=8082 )