FROM python:3.10-slim

USER root
RUN apt update ; \
  apt upgrade -y ; \
  apt install -y openssh-client sshpass; \
  apt -y install make; \
  apt -y install vim; \
  apt -y install nano; \
  pip install netaddr ansible==10.3.0 cryptography==46.0.7; \
  ln -sf /bin/bash /bin/sh;

RUN mkdir /ansible && mkdir -p /ansible/.ssh

WORKDIR /ansible

COPY ./requirements.yml /ansible/requirements.yml
RUN ansible-galaxy role install -r /ansible/requirements.yml -p /ansible/galaxy_roles \
 && ansible-galaxy collection install -r /ansible/requirements.yml

# Inventory, group_vars, host_vars and init_script are bind-mounted at runtime
# (see docker-compose.yml) so they are intentionally not COPYed into the image,
# which would otherwise bake secrets into the layers.
COPY ./playbooks /ansible/playbooks
COPY ./roles /ansible/roles
COPY ./docker/docker-entrypoint.sh /ansible/docker-entrypoint.sh

ENTRYPOINT [ "/ansible/docker-entrypoint.sh" ]
