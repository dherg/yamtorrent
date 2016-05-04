import sys
import bencode

def main():

	# open file in binary
	torrentfile = open(sys.argv[1], "rb").read()

	# dictionary of torrent file
	torrentdict = bencode.bdecode(torrentfile)
	print(torrentdict)

if __name__ == "__main__":
	main()
