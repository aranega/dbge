DIR = ./dbge/frame_access

all: $(DIR)/frame_access.so

$(DIR)/frame_access.so: $(DIR)/frame_access.c
	gcc -shared -o $(DIR)/frame_access.so $(DIR)/frame_access.c -I/usr/include/python3.11/