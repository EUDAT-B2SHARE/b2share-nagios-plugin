FROM rockylinux:9
# eudat-docker.artifactory.ci.csc.fi/

LABEL maintainer Giacomo Furlan <giacomo.furlan@csc.fi>
LABEL description="Image to test nagios plugin on eudat b2share instances."

RUN dnf update -y && \
    dnf install -y python3.9 && \
    dnf install -y python3.9-pip

WORKDIR /root

ADD check_b2share.py check_b2share.py
ADD requirements.txt requirements.txt

RUN pip3 install -r requirements.txt
