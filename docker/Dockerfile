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

# Inventory, group_vars, host_vars, init_script, playbooks and roles are all
# bind-mounted at runtime (see docker-compose.yml), so nothing from the repo is
# COPYed here: it would bake secrets and vendored roles into the image layers
# while being shadowed by the mounts anyway. External roles/collections come from
# the ansible-galaxy install above.
COPY ./docker/docker-entrypoint.sh /ansible/docker-entrypoint.sh

# Marker used by the Makefile to refuse operational targets on the host.
ENV IN_PYRO_ANSIBLE_CONTAINER=1

ENTRYPOINT [ "/ansible/docker-entrypoint.sh" ]
