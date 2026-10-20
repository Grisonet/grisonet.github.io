#!/bin/bash
# Publica a pasta apuracao-sp/ no repositório Grisonet/apuracao (GitHub Pages em apuracao.grisodata.com.br).
# Copia só o retrato atual da pasta, num commit novo, sem histórico. Roda sozinho pelo hook pre-push:
#   ln -sf ../../apuracao-sp-fonte/publica-apuracao.sh .git/hooks/pre-push
# Ou na mão: apuracao-sp-fonte/publica-apuracao.sh [commit]
set -euo pipefail
REPO="$(git rev-parse --show-toplevel)"
DESTINO="git@github.com:Grisonet/apuracao.git"
# o domínio só entra (arquivo CNAME) depois que o DNS estiver no ar: git config apuracao.dominio apuracao.grisodata.com.br
DOMINIO="$(git config apuracao.dominio || true)"

# no pre-push, o git passa no stdin as refs enviadas; publica o que vai para main
REF="${1:-}"
if [ -z "$REF" ] && [ ! -t 0 ]; then
  while read -r _ local_sha remote_ref _; do
    [ "$remote_ref" = "refs/heads/main" ] && REF="$local_sha"
  done
  [ -z "$REF" ] && exit 0
fi
REF="${REF:-HEAD}"
[ "$REF" = "0000000000000000000000000000000000000000" ] && exit 0

cd "$REPO"
ARVORE=$(git rev-parse "$REF:apuracao-sp")
if [ -n "$DOMINIO" ]; then
  CNAME=$(printf '%s\n' "$DOMINIO" | git hash-object -w --stdin)
  ARVORE=$( { git ls-tree "$ARVORE" | grep -v $'\tCNAME$'; printf '100644 blob %s\tCNAME\n' "$CNAME"; } | git mktree)
fi
COMMIT=$(git commit-tree "$ARVORE" -m "publica apuracao-sp de $(git rev-parse --short "$REF")")
git push --quiet --force "$DESTINO" "$COMMIT:refs/heads/main" \
  && echo "apuração publicada em ${DOMINIO:-grisonet.github.io/apuracao} ($(git rev-parse --short "$REF"))" >&2 \
  || echo "⚠️  não consegui publicar no Grisonet/apuracao; rode apuracao-sp-fonte/publica-apuracao.sh" >&2
exit 0
