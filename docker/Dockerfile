FROM python:3.10-slim

USER root
RUN apt update ; \
  apt upgrade -y ; \
  apt install -y openssh-client; \
  apt -y install make; \
  apt -y install vim; \
  apt -y install nano; \
  pip install netaddr; \
  pip install ansible==10.3.0; \
  ln -sf /bin/bash /bin/sh;

RUN mkdir /ansible && mkdir -p /ansible/.ssh

WORKDIR /ansible

COPY ./group_vars /ansible/group_vars
COPY ./hooks /ansible/hooks
COPY ./init_script /ansible/init_script
COPY ./inventory /ansible/inventory
COPY ./playbooks /ansible/playbooks
COPY ./roles /ansible/roles
COPY ./docker/docker-entrypoint.sh /ansible/docker-entrypoint.sh

ENTRYPOINT [ "/ansible/docker-entrypoint.sh" ]