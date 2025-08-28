FROM python:3.10-slim

RUN apt-get update -y && ACCEPT_EULA=Y apt-get install -y --allow-downgrades \
    curl  vim gcc g++ procps iputils-ping net-tools telnet git nodejs npm && rm -rf /var/lib/apt/lists/*

SHELL ["/bin/bash", "-c"]

ADD before_files /

RUN cd /backend && pip3 install -r requirements.txt
RUN cd /frontend && npm install

ADD after_files /

RUN chmod +x /init.sh
ENTRYPOINT [ "/init.sh" ]

