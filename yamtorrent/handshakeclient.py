import struct
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ClientFactory
from twisted.internet.protocol import Protocol
from twisted.internet import reactor


class HandshakeClient(Protocol):

    def __init__(self, info_hash, peer_id):
        self.info_hash = info_hash
        self.peer_id = peer_id

    def sendMessage(self):
        msg = struct.pack('!B', 19) + b"BitTorrent protocol" + bytearray(8) + self.info_hash + self.peer_id
        self.transport.write(msg)

    # overridden from twisted.protocol.Protocol
    def connectionMade(self):
        self.sendMessage()

    # overridden from twisted.protocol.Protocol
    def dataReceived(self, data):
        print("receive:", data)
        self.transport.loseConnection()


class HandshakeClientFactory(ClientFactory):

    def __init__(self, info_hash, peer_id):
        self.done = Deferred()
        self.info_hash = info_hash
        self.peer_id = peer_id

    def buildProtocol(self, address):
        return HandshakeClient(self.info_hash, self.peer_id)

    def clientConnectionFailed(self, connector, reason):
        print('connection failed:', reason.getErrorMessage())
        self.done.errback(reason)

    def clientConnectionLost(self, connector, reason):
        print('connection lost:', reason.getErrorMessage())
        self.done.callback(None)


def connectHandshakeClient(host, port, info_hash, peer_id):
    factory = HandshakeClientFactory(info_hash, peer_id)
    reactor.connectTCP(host, port, factory)
    reactor.run()
