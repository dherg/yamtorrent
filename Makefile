JFLAGS = -g
JC = javac
.SUFFIXES: .java .class
.java.class:
	$(JC) $(JFLAGS) $*.java

CLASSES = \
	YamTorrent.java \
	BencodeReader.java \
	BencodeWriter.java \
	BencodeReadException.java

default: classes

classes: $(CLASSES:.java=.class)

clean:
	$(RM) *.class
