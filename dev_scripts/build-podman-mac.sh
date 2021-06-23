#!/bin/bash

PODMAN_URL=https://github.com/containers/podman/archive/v3.2.1.tar.gz
PODMAN_SHA256=140cbe8d6cb7807cbd3ef6d549d888e1c0e44d32dcff3a27453630fc52e7f5b8
PODMAN_FILENAME=v3.2.1.tar.gz
PODMAN_DIRNAME=podman-3.2.1

mkdir -p build/podman
cd build/podman

# Download file
if [ -f $PODMAN_FILENAME ]; then
    echo File already exists, skipping download
else
    wget $PODMAN_URL
fi

# Verify checksum
if shasum -a 256 $PODMAN_FILENAME | grep $PODMAN_SHA256; then
    echo Checksum verified
else
    echo Checksum failed
    exit
fi

# Extract
rm -rf $PODMAN_DIRNAME
tar -xf $PODMAN_FILENAME
echo Extracted source

# Build
cd $PODMAN_DIRNAME
make podman-remote-darwin

# Copy into share
cd ../../..
mkdir -p share/bin
cp build/podman/podman-3.2.1/bin/darwin/podman share/bin/podman
