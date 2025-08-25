FROM python:3.11-slim

RUN apt-get update -y && ACCEPT_EULA=Y apt-get install -y --allow-downgrades \
    curl  vim gcc g++ procps iputils-ping net-tools telnet git nodejs npm && rm -rf /var/lib/apt/lists/*

RUN pip3 install asyncio websockets requests openai

SHELL ["/bin/bash", "-c"]

ADD after_files /

RUN cd frontend && npm install

#WORKDIR frontend
RUN chmod +x /init.sh
ENTRYPOINT [ "/init.sh" ]

