#!/usr/bin/env python3
import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from twisted.internet import reactor
from yamtorrent import PeerInfo, TorrentMetadata, PeerConnection, TorrentFile

def DEBUG(*s):
    if debugging:
        print(*s)


def ERROR(*s):
    print(*s)
    exit()

def main():
    # open file in binary
    torrent = None
    try:
        filename = sys.argv[1] if len(sys.argv) > 0 else None
        torrent = TorrentFile(filename)
    except FileNotFoundError:
        ERROR("BAD FILE NAME: " + filename)

    DEBUG("BEGINNING")

    # dictionary of torrent file
    torrentdict = torrent.torrent_dict
    info_hash = torrent.info_hash
    info = torrent.info

    peer_id = b"-YT0001-" + os.urandom(12)
    port = b'6881'
    uploaded = b'0'
    downloaded = b'0'

    left = torrent.get_length()
    print("left:", left)

    compact = b'1'
    event = b'started'

    url = torrentdict[b'announce']

    p = {'info_hash': info_hash, 'peer_id': peer_id, 'port': port, 'uploaded': uploaded, 'downloaded': downloaded, 'left': left, 'compact': compact, 'event': event}

    #CONTACT TRACKER
    r = requests.get(url.decode(), params=p)

    # print(info_hash)
    # print(bencodedinfo)

    # with open("temp.txt",'wb') as f:
    #   f.write(r.text.encode())

    DEBUG('URL')
    DEBUG(r.url)
    DEBUG('END URL')
    DEBUG('CONTENT')
    DEBUG(r.content)
    DEBUG('END CONTENT')

    try:
        response = bencodepy.decode(r.content)
    except bencodepy.exceptions.DecodingError:
        ERROR("BAD RESPONSE")

    #COMPUTE PEERS
    torrent_meta = TorrentMetadata(info_hash, peer_id)

    peers = response[b'peers']
    peers_list = []
    for i in range(0, len(peers), 6):

        peer_info = PeerInfo(ip=socket.inet_ntoa(peers[i:i+4]),
                             port=struct.unpack("!H", peers[i+4:i+6])[0])

        peers_list.append(peer_info)

    DEBUG(list(map(str, peers_list)))

    first_peer = PeerConnection(torrent_meta, peers_list[0])
    # first_connection = socket.create_connection((first_peer['ip'],first_peer['port']))
    # DEBUG(type(first_connection))

    first_peer.connect(reactor)

    reactor.run()

    # handshake = struct.pack('!B',19) + b"BitTorrent protocol" + bytearray(8) + info_hash + peer_id
    # DEBUG(handshake)
    # DEBUG(len(handshake))
    # DEBUG(len(info_hash))
    # DEBUG(len(peer_id))

    # first_connection.sendall(handshake)

    # peer_response = first_connection.recv(4096)

    # DEBUG("handshake response", peer_response)



if __name__ == '__main__':

    debugging = True

    main()
