#!/bin/bash
# Apre sul Mac la chat (http://localhost:8080) e l'agente (http://localhost:3000) di DeepSeek su ReCaS.
# Trova da solo il lavoro acceso e si ricollega se la rete cambia. Si chiude con ctrl-C.
T=/lustrehome/climpact/trace/chat/t; S=/lustrehome/climpact/trace/chat/s
while true; do
  JOB=$(ssh -o BatchMode=yes recas "condor_q climpact -constraint 'JobStatus==2' -af ClusterId Cmd | grep avvio2 | head -1 | cut -d' ' -f1" < /dev/null)
  if [ -z "$JOB" ]; then echo "DeepSeek non e' acceso su ReCaS: riprovo fra un minuto"; sleep 60; continue; fi
  echo "collegato al lavoro $JOB: chat su http://localhost:8080, agente su http://localhost:3000"
  ssh -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
    -L 8080:$T/webui.sock -L 3000:$T/oh.sock recas \
    "mkdir -p $T; chmod 700 $T; rm -f $T/webui.sock $T/oh.sock; condor_ssh_to_job -ssh 'ssh -N -o StreamLocalBindUnlink=yes -L $T/webui.sock:$S/webui.sock -L $T/oh.sock:$S/oh.sock' $JOB"
  echo "collegamento caduto $(date), riapro fra 5 s"; sleep 5
done
