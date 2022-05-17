#!/usr/bin/env bash

BASE_FOLDER="$( dirname "${0}" )" 

echo -n "Build HTML version or PDF version (h/p)? The PDF version has a larger image size (>1.5GB):"
read BUILD_TYPE
if [ "$BUILD_TYPE" == "p" ]; then
    BASE_IMAGE=sphinxdoc/sphinx-latexpdf:latest
    IMAGE_NAME=danwos/sphinxneeds-latexpdf:latest    
    echo "Building PDF Image..."
else
    BASE_IMAGE=sphinxdoc/sphinx:latest
    IMAGE_NAME=danwos/sphinxneeds:latest
    echo "Building HTML Image..."
fi


echo " -----------------------  HINT  ----------------------"
echo "| Setting up Sphinx Needs Version.                    |"
echo "| Leave the field empty for the latest release,       |"
echo "| a version number (eg, 0.7.8) for a specific release,|"
echo "| or 'pre-release' for the upcoming release           |"
echo " ----------------------------------------------------- "
if [[ -z "$NEEDS_VERSION" ]]; then
    echo -n Sphinx Needs Version:
    read NEEDS_VERSION
fi     

DOCKER_BUILDKIT=1 docker build --no-cache \
    --progress=plain \
    --build-arg NEEDS_VERSION=$NEEDS_VERSION \
    --build-arg BASE_IMAGE=$BASE_IMAGE \
    -f Dockerfile \
    -t $IMAGE_NAME \
    ${BASE_FOLDER}
