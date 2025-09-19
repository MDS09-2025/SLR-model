#!/bin/bash

URL="https://github.com/SignBridgeApp/models/releases/download/v0.0/gloss2pose.zip"
ZIP_FILE="gloss2pose.zip"
TARGET_DIR="gloss2pose"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Downloading and extracting $ZIP_FILE..."

	if [ ! -d "$ZIP_FILE" ]; then
    	wget -q "$URL"
	else
    	echo "Zip $ZIP_FILE already exists. Skipping download."
	fi

	unzip -q "$ZIP_FILE" && rm "$ZIP_FILE"
	echo "Done."
else
    echo "Directory $TARGET_DIR already exists. Skipping download and extraction."
fi

git clone https://github.com/SignBridgeApp/pose-all.git
cd pose-all/src/python && pip3 install .
rm -rf pose-all/

# apt install -y libgl1-mesa-glx
# ldconfig