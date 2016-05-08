#!/usr/bin/env python3
import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from twisted.internet import reactor
from yamtorrent import PeerInfo, TorrentMetadata, PeerConnection

def DEBUG(*s):
    if debugging:
        print(*s)


def ERROR(*s):
    print(*s)
    exit()

def main():
    peer_id = b"-YT0001-" + os.urandom(12)
    meta_info = None
    try:
        filename = sys.argv[1] if len(sys.argv) > 0 else None
        meta_info = TorrentMetadata(filename, peer_id)
    except FileNotFoundError:
        ERROR("BAD FILE NAME: " + filename)

    DEBUG("BEGINNING")

    # dictionary of torrent file
    info_hash = meta_info.info_hash()

    port = b'6881'
    uploaded = b'0'
    downloaded = b'0'

    left = meta_info.full_length()
    print("left:", left)

    compact = b'1'
    event = b'started'

    url = meta_info.announce()

    p = {'info_hash': info_hash,
         'peer_id': peer_id,
         'port': port,
         'uploaded': uploaded,
         'downloaded': downloaded,
         'left': left,
         'compact': compact,
         'event': event}

    # CONTACT TRACKER
    r = requests.get(url.decode(), params=p)

    try:
        response = bencodepy.decode(r.content)
    except bencodepy.exceptions.DecodingError:
        ERROR("BAD RESPONSE")

    def make_peer(peer_data):
        return PeerInfo(ip=socket.inet_ntoa(peer_data[0]),
                        port=peer_data[1])
    peers = list(map(make_peer, struct.iter_unpack('!4sH', response[b'peers'])))

    print('Tracker returned', len(peers), 'peers.')

    print('Connecting to peer:', str(peers[0]))
    first_peer = PeerConnection(meta_info, peers[0])
    first_peer.connect(reactor)

    reactor.run()


if __name__ == '__main__':
    debugging = True
    main()
