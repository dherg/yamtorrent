/* 	YamTorrent.java
*
* 	David Hergenroeder (david.hergenroeder@yale.edu)
* 
*
*/

import java.lang.*;
import java.io.*;
import java.util.*;

class YamTorrent {

	public static int readBencodedFile(String filename) {

		// open up filename
		File f = new File(filename);


		// turn it into an InputStream
		InputStream fileStream;
		try {
			fileStream = new FileInputStream(f);
		} catch (FileNotFoundException e) {
			System.err.println("Error: file not found");
			e.printStackTrace();
			return null;
		}

		// create a new BencodeReader
		BencodeReader reader = new BencodeReader(fileStream);

		// torrent files are bencoded dict, so read the overall dict
		Map<String, Object> dict;
		try {
			dict = reader.readDict();
		} catch (Exception e) {
			System.err.println("Error reading torrent file");
			e.printStackTrace();
			return null;
		}

		// test print dict
		System.out.println(dict);


		// return 0 for no error
		return dict;
	}

	public static void main(String args[]) {
		
		System.out.println("down with yam, up with lamb");

		// Get the torrent file name from args
		String filename = args[0];

		System.out.println("filename = " + filename);

		Map<String, Object> dict;
		dict = readBencodedFile(filename);
		if (dict == null) {
			System.err.println("Error reading torrent file \"" + filename + "\"");
			return;
		}

		// use dictionary to start downloading file



	} // end of main

} // end of class YamTorrent
