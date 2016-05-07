#!/usr/bin/env python3
import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import yamtorrent.handshakeclient as handshakeclient

def DEBUG(*s):
    if debugging:
        print(*s)


def ERROR(*s):
    print(*s)
    exit()

def main():
    # open file in binary
    try:
        torrentfile = open(sys.argv[1], "rb").read()
    except IOError:
        ERROR("BAD FILE NAME: " + sys.argv[1])

    DEBUG("BEGINNING")

    # dictionary of torrent file
    # torrentdict = bencode.bdecode(torrentfile)
    torrentdict = bencodepy.decode(torrentfile)
    # print(torrentdict)
    # print(type(torrentdict))

    # re-bencode the info section
    info = torrentdict[b"info"]
    # print(info)
    bencodedinfo = bencodepy.encode(info)
    # print(info)
    # print(bencodedinfo)

    #COMPUTE PARAMETERS FOR ANNOUNCE

    # SHA1 hash of info section
    sha1 = hashlib.sha1(bencodedinfo)
    info_hash = sha1.digest()
    # print(type(bencodedinfo))
    # for char in info_hash:
    #   print(hex(char))
    #   print(char)

    peer_id = (hashlib.sha1(b"0")).digest()
    port = b'6881'
    uploaded = b'0'
    downloaded = b'0'

    try:
        left = 0
        for f in info[b'files']:
            left += f[b'length']
    except KeyError:
        left = info[b'length']

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

    peers = response[b'peers']
    peers_list = []
    for i in range(0,len(peers),6):

        peer_dict = {}

        #not sure if these are right
        peer_dict['ip'] = socket.inet_ntoa(peers[i:i+4])
        peer_dict['ip_int'] = struct.unpack("!L",peers[i:i+4])[0]
        peer_dict['port'] = struct.unpack("!H",peers[i+4:i+6])[0]

        peers_list.append(peer_dict)

    DEBUG(peers_list)

    first_peer = peers_list[0]
    # first_connection = socket.create_connection((first_peer['ip'],first_peer['port']))
    # DEBUG(type(first_connection))

    handshakeclient.connectHandshakeClient(first_peer['ip'], first_peer['port'], info_hash, peer_id)

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
