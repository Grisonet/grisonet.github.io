#!/bin/zsh
# Noite do 2º turno (25/10/2026): coleta no Mac e envia ao relay do Railway.
#   iniciar:  ~/eleicao2026/projecao/noite.sh          (deixa rodando em segundo plano)
#   parar:    pkill -f "projecao/noite.sh"; pkill -f "projecao/coletor.py"
#   log:      tail -f ~/eleicao2026/projecao/out/noite.log
cd "$(dirname "$0")"
set -a; source ~/.config/grdata/relay.env; set +a
export REQ_POR_SEG=${REQ_POR_SEG:-110} THREADS=${THREADS:-128} LOTE=${LOTE:-4000} INTERVALO=${INTERVALO:-30}
mkdir -p out
if [[ "$1" != "--fg" ]]; then
  nohup caffeinate -i "$0" --fg >> out/noite.log 2>&1 &
  echo "rodando em segundo plano — log: $(pwd)/out/noite.log"
  exit 0
fi
while true; do                       # reinicia sozinho se o coletor cair
  python3 -u "$(pwd)/coletor.py"
  echo "$(date +%T) coletor saiu ($?) — reiniciando em 5 s"
  sleep 5
done
