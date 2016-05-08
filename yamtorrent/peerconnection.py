import struct
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ClientFactory
from twisted.internet.protocol import Protocol
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ClientEndpoint
from enum import Enum


class PeerConnection(object):

    class _States(Enum):
        WAIT_CONNECT = 0
        WAIT_HANDSHAKE = 1
        WAIT_BITFIELD = 2
        WIRE = 3

    def __init__(self, meta, peer_info, protocol=None):
        self.meta = meta
        self.peer_info = peer_info
        self.bitfield = None
        self.state = self._States.WAIT_CONNECT
        self._protocol = protocol

    def connect(self, reactor):
        self.done = Deferred()
        d = (TCP4ClientEndpoint(reactor, self.peer_info.ip, self.peer_info.port)
                     .connect(ProtocolAdapterFactory(self)))
        # d.addErrback(self.connection_failed)
        self.state = self._States.WAIT_CONNECT

        return d

    def request_handshake(self):
        msg = struct.pack('!B', 19) + b"BitTorrent protocol" + bytearray(8) + self.meta.info_hash + self.meta.peer_id
        self._protocol.tx_data(msg)
        self.state = self._States.WAIT_HANDSHAKE

    def rcv_handshake(self, data):
        print('rcv_handshake:', data)
        pass

    def request_bitfield(self):
        # construct message
        msg = bytearray(2)
        # self.transport.write(msg)
        self.state = self._States.WAIT_BITFIELD

    def rcv_bitfield(self, data):
        # parse bitfield
        # store bitfield locally
        # print('rcv_bitfield:', data)
        bitfield = ()
        # self.done.callback(bitfield)

    # this is called async by your event loop
    def rx_data(self, data):

        # parse data here
        if self.state == self._States.WAIT_HANDSHAKE:
            self.rcv_handshake(data)
            self.request_bitfield()
        elif self.state == self._States.WAIT_BITFIELD:
            self.rcv_bitfield(data)
        else:
            # unknown message
            pass

    def did_connect(self, protocol):
        self._protocol = protocol
        self.request_handshake()

    def connection_lost(self):
        print('connection lost!')


class ProtocolAdapter(Protocol):

    def __init__(self, delegate):
        self._delegate = delegate

    def tx_data(self, data):
        self.transport.write(data)

    # overridden from twisted.protocol.Protocol
    def dataReceived(self, data):
        if self._delegate is not None:
            self._delegate.rx_data(data)

    # overridden from twisted.protocol.Protocol
    def connectionMade(self):
        if self._delegate is not None:
            self._delegate.did_connect(self)

    def connectionLost(self, reason):
        if self._delegate is not None:
            self._delegate.connection_lost()

    def stop(self):
        self.transport.loseConnection()


class ProtocolAdapterFactory(ClientFactory):

    def __init__(self, delegate):
        self.done = Deferred()
        self._delegate = delegate

    def buildProtocol(self, address):
        return ProtocolAdapter(self._delegate)
