#!/bin/bash
# 01/10/2026: ogni 20 minuti scarica le letture P05 (le due meta' di Neubauer, sui due DeepSeek), le unisce e
# ricarica le proposte di Neubauer e Future Generations; finisce con un ultimo caricamento e il controllo.
cd ~/sabin-corpus; P=training/principi
giro() {
  for c in neubauer future-generations; do for s in P05 l04P05; do
    scp -q recas:trace/training/principi/${c}_ripresa_deepseek_$s.jsonl $P/${c}_ripresa_deepseek_$s.jsonl.a 2>/dev/null || continue
    if [ $c = neubauer ]; then scp -q recas:trace/training/principi/${c}_ripresa_deepseek_${s}b.jsonl $P/${c}_ripresa_deepseek_${s}b.jsonl 2>/dev/null; cat $P/${c}_ripresa_deepseek_$s.jsonl.a $P/${c}_ripresa_deepseek_${s}b.jsonl 2>/dev/null > $P/${c}_ripresa_deepseek_$s.jsonl
    else mv $P/${c}_ripresa_deepseek_$s.jsonl.a $P/${c}_ripresa_deepseek_$s.jsonl; fi
    rm -f $P/${c}_ripresa_deepseek_$s.jsonl.a
  done
  for i in 1 2 3; do TRACE_SONDE=P05 .venv/bin/python tools/035_carica_ripresa.py --caso $c --principi-da-l04 --anche-senza-lettura --scrivi > /tmp/ciclo_p05_$c.txt 2>&1 && break; sleep 30; done
  echo "$(date +%H:%M) $c: $(grep -h 'provvisoria' /tmp/ciclo_p05_$c.txt | tr -d ' ,') $(grep '^scritte' /tmp/ciclo_p05_$c.txt)"
  done
}
while true; do
  giro
  if ssh -o ConnectTimeout=25 recas 'test -s ~/trace/chat/log/p05_fine.txt && test -s ~/trace/chat/log/p05b_fine.txt' 2>/dev/null; then giro; break; fi
  sleep 1200
done
for i in 1 2 3; do .venv/bin/python tools/036_controllo_completezza.py --scrivi > /tmp/ciclo_p05_controllo.txt 2>&1 && break; sleep 30; done
cat /tmp/ciclo_p05_controllo.txt; echo "CICLO P05 FINITO $(date +%H:%M)"
