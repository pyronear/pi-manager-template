FROM python:3.10-slim

USER root
RUN apt update ; \
  apt upgrade -y ; \
  apt install -y openssh-client; \
  apt -y install make; \
  apt -y install vim; \
  pip install netaddr; \
    pip install ansible==10.3.0;

RUN mkdir /ansible && mkdir -p /ansible/.ssh

WORKDIR /ansible

COPY .. /ansible

ENTRYPOINT [ "sh" ]