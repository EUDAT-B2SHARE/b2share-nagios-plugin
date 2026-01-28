FROM rockylinux:9
# eudat-docker.artifactory.ci.csc.fi/

LABEL maintainer="Giacomo Furlan <giacomo.furlan@csc.fi>"
LABEL maintainer="Petri Laihonen <petri.Laihonen@csc.fi>"
LABEL description="Image to test nagios plugin on eudat b2share instances."

RUN dnf update -y && \
    dnf install -y python3.12 python3.12-pip && \
    ln -s /usr/bin/pip-3.12 /usr/bin/pip3

WORKDIR /root

ADD *.py ./
ADD requirements.txt requirements.txt
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

RUN python3 -m venv .venv && \
    . .venv/bin/activate && \
    pip3 install -r requirements.txt && \
    chmod 755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

CMD ["bash"]
