#!/usr/bin/env python3
import sys
import requests
import hashlib
import bencodepy
import struct
import socket
import os
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import getPage

from yamtorrent import PeerInfo, TorrentMetadata, PeerConnection, TrackerConnection, TorrentManager

def DEBUG(*s):
    if debugging:
        print(*s)


def ERROR(*s):
    print(*s)
    exit()

def main():
    port = b'6881'
    peer_id = b'-YT0001-' + os.urandom(12)
    meta_info = None
    try:
        filename = sys.argv[1] if len(sys.argv) > 0 else None
        meta_info = TorrentMetadata(filename, peer_id)
    except FileNotFoundError:
        ERROR('INVALID FILE NAME: ' + filename)

    torrent = TorrentManager(meta_info, port, peer_id)
    torrent.start()


if __name__ == '__main__':
    debugging = True
    main()
