# Dockerfile for Sphinx-Needs
# syntax = docker/dockerfile:1.2
ARG BASE_IMAGE=sphinxdoc/sphinx:latest
FROM $BASE_IMAGE
LABEL maintainer="useblocks <https://useblocks.com/>"

ARG DOCKER_USERNAME=dockeruser
ARG DOCKER_USER_ID=1000
ARG DOCKER_GROUP_ID=$DOCKER_USER_ID
ARG NEEDS_VERSION

# To prevent interactive shells
ARG DEBIAN_FRONTEND=noninteractive

# Install apt & make
RUN \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y --no-install-recommends sudo

# Create user
RUN groupadd -g ${DOCKER_GROUP_ID} ${DOCKER_USERNAME} &&\
    useradd -l -u ${DOCKER_USER_ID} -g ${DOCKER_USERNAME} ${DOCKER_USERNAME} &&\
    install -d -m 0755 -o ${DOCKER_USERNAME} -g ${DOCKER_USERNAME} /home/${DOCKER_USERNAME} &&\
    echo $DOCKER_USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$DOCKER_USERNAME &&\
    chmod 0440 /etc/sudoers.d/$DOCKER_USERNAME &&\    
    chown -R ${DOCKER_USERNAME} /home/${DOCKER_USERNAME}

# Install some basic tooling
RUN apt-get -y --no-install-recommends install \
  wget \
  git

# Install PlantUML dependencies
RUN apt-get -y install \
  default-jre

# Install PlantUML
RUN wget -c https://netcologne.dl.sourceforge.net/project/plantuml/plantuml.jar -O /tmp/plantuml.jar && \
    mkdir -p /usr/share/plantuml && \
    mv /tmp/plantuml.jar /usr/share/plantuml/plantuml.jar

# Install needed sphinx components
RUN pip3 install --no-cache-dir \
  sphinxcontrib-plantuml 

# Install Sphinx-Needs
RUN \
    if [ -n "$NEEDS_VERSION" ] && [ "$NEEDS_VERSION" = "pre-release" ]; then \
      pip3 install --no-cache-dir "sphinx-needs[plotting] @ git+https://github.com/useblocks/sphinx-needs"; \
    elif [ -n "$NEEDS_VERSION" ]; then \
      pip3 install --no-cache-dir "sphinx-needs[plotting] @ git+https://github.com/useblocks/sphinx-needs@$NEEDS_VERSION"; \
    else \
      pip3 install --no-cache-dir sphinx-needs[plotting]; \
    fi

## Clean up
RUN apt-get remove -y wget \
git

WORKDIR /sphinxneeds

 # Start as user
USER ${DOCKER_USERNAME}