#!/bin/bash

set -e
mkdir -p $HOME/.ssh
cp /ansible/id_rsa $HOME/.ssh/id_rsa
cp /ansible/.vault_passwrd $HOME/.vault_passwrd

echo "Modification permission"
chmod 600 $HOME/.ssh/id_rsa
chmod 700 $HOME/.ssh
chmod 600 $HOME/.vault_passwrd

exec "$@"