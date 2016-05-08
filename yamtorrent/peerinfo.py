class PeerInfo:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def __str__(self):
        return '{}:{}'.format(self.ip, self.port)

    def __repr__(self):
        return '<PeerInfo object {}>'.format(str(self))