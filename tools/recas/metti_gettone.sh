#!/bin/bash
# Scrive ~/.kube/config per il cluster GPU di ReCaS-Bari con il gettone personale
# (https://auth-k8s.recas.ba.infn.it, dura 7 giorni). Il gettone si incolla qui e
# non compare a schermo: non passa dalla chat.
set -e
mkdir -p ~/.kube
if [ -f ~/.kube/config ] && ! grep -q "k8s.recas.ba.infn.it" ~/.kube/config; then
  cp ~/.kube/config ~/.kube/config.prima-di-recas
  echo "C'era gia' un ~/.kube/config: copiato in ~/.kube/config.prima-di-recas"
fi
printf 'Incolla il gettone di ReCaS e premi Invio: '
read -s GETTONE; echo
[ -n "$GETTONE" ] || { echo "Gettone vuoto, niente scritto."; exit 1; }
cat > ~/.kube/config <<CFG
apiVersion: v1
kind: Config
preferences: {}
clusters:
- name: default
  cluster:
    server: https://k8s.recas.ba.infn.it:443
contexts:
- name: oidc-user-context
  context:
    cluster: default
    user: oidc-user
    namespace: batch-climpact
current-context: oidc-user-context
users:
- name: oidc-user
  user:
    token: $GETTONE
CFG
chmod 600 ~/.kube/config
unset GETTONE
echo "Fatto. Prova:"
kubectl get pod
