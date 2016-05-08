from .peerconnection import PeerConnection
from .torrentfile import TorrentFile


class PeerInfo:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def __str__(self):
        return '{}:{}'.format(self.ip, self.port)

    def __repr__(self):
        return '<PeerInfo object {}>'.format(str(self))


class TorrentMetadata:
    def __init__(self, info_hash, peer_id):
        self.info_hash = info_hash
        self.peer_id = peer_id
