import sys
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
        LATER = 2

    def __init__(self, meta, peer_info, protocol=None):
        self.meta = meta
        self.peer_info = peer_info
        self.bitfield = None
        self.state = self._States.WAIT_CONNECT
        self._protocol = protocol
        self.buf = bytearray()

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
        print(len(data))
        pass

    # NOT USING RIGHT NOW
    def send_bitfield(self):
        # construct message
        msg = bytearray(2)
        # self.transport.write(msg)
        # self.state = self._States.WAIT_BITFIELD

    def rcv_keepalive(self):
        print('rcv_keepalive')
        # we probably should reset a timer or something
        pass

    def rcv_choke(self, msg, msg_length):
        print('rcv_choke', msg_length)
        pass

    def rcv_unchoke(self, msg, msg_length):
        print('rcv_unchoke', msg_length)
        pass

    def rcv_interested(self, msg, msg_length):
        print('rcv_interested', msg_length)
        pass

    def rcv_notinterested(self, msg, msg_length):
        print('rcv_notinterested', msg_length)
        pass

    def rcv_have(self, msg, msg_length):
        print('rcv_hav', msg_length)
        pass

    def rcv_bitfield(self, msg, msg_length):
        # parse bitfield
        # store bitfield locally
        print('rcv_bitfield:', msg)
        # message_length = struct.unpack(">i",msg[:4])[0]
        # print('length', message_length)
        # print(len(msg))
        # print(msg[0])
        # print(msg[1])
        # print(msg[2])
        # print(msg[3])
        # print(msg[4])
        # print(msg[0:5])
        # print(len(msg[0:5]))
        bitfield = ()
        # self.done.callback(bitfield)

    def rcv_request(self, msg, msg_length):
        print('rcv_request', msg_length)
        pass

    def rcv_piece(self, msg, msg_length):
        print('rcv_piece', msg_length)
        pass

    def rcv_cancel(self, msg, msg_length):
        print('rcv_cancel', msg_length)
        pass

    def rcv_port(self, msg, msg_length):
        print('rcv_port', msg_length)
        pass


    def process_buf(self):


        #if this should a received handshake
        if (len(self.buf) > 0) and (len(self.buf) >= 49 + self.buf[0]) and (self.state == self._States.WAIT_HANDSHAKE):
            
            pstrlen = self.buf[0]
            pstr = self.buf[1:pstrlen + 1]
            reserved = self.buf[pstrlen + 1:pstrlen + 9]
            info_hash = self.buf[pstrlen + 9:pstrlen+29]
            peer_id = self.buf[pstrlen+29:pstrlen+49]

            #check that this is the handshake receipt
            if (pstr == b"BitTorrent protocol") and (info_hash == self.meta.info_hash):
                
                self.state = self._States.LATER
                data = self.buf[:pstrlen+49]

                self.buf = self.buf[pstrlen+49:]
                print('handshake match.')

                return data,0

            else:
                print('PROBABLY SHOULD DROP CONNECTION B/C BAD HANDSHAKE')

        


        #if we don't even have a length at the start
        if len(self.buf) < 4:
            return None,0

        msg_length = struct.unpack("!i",self.buf[:4])[0]

        print('process_buf len=', len(self.buf), 'want=', msg_length, 'type = ', self.buf[4])


        #if we have the full message in the buffer
        if len(self.buf) >= 4 + msg_length:
            data = self.buf[:msg_length+4]

            #remove message from buffer
            self.buf = self.buf[msg_length+4:]

            return data,msg_length

        return None,0

    def handle_message(self, msg, msg_length):

        # if this is a keep-alive
        if msg_length == 0:
            self.rcv_keepalive()
            return None

        msg_type = msg[4]

        options = {
            0: self.rcv_choke,
            1: self.rcv_unchoke,
            2: self.rcv_interested,
            3: self.rcv_notinterested,
            4: self.rcv_have,
            5: self.rcv_bitfield,
            6: self.rcv_request,
            7: self.rcv_piece,
            8: self.rcv_cancel,
            9: self.rcv_port
        }

        options[msg_type](msg, msg_length)






    # this is called async by your event loop
    def rx_data(self, data):

        self.buf += data

        next_message, msg_length = self.process_buf()
        print(next_message, msg_length)

        if next_message is not None:
            self.handle_message(next_message, msg_length)

        # # parse data here
        # if self.state == self._States.WAIT_HANDSHAKE:
        #     self.rcv_handshake(data)
        #     self.request_bitfield()
        # elif self.state == self._States.WAIT_BITFIELD:
        #     self.rcv_bitfield(data)
        # else:
        #     # unknown message
        #     pass

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
