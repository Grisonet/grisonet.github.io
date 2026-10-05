#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera apuracao-sp/index.html a partir de web-src/sp2026.html.
O sp2026.html é escrito no formato "Artifact" (começa com <title>/<link>/<style>
e depois o corpo, SEM <!doctype>/<head>/<body>). Este script embrulha num
documento HTML completo. Rode e copie o resultado para apuracao-sp/index.html.
Uso:  python3 build_index.py            # gera index.html ao lado
"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "sp2026.html"), encoding="utf-8").read()
i = src.index("</style>") + len("</style>")
head, body = src[:i], src[i:]
doc = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
       + head + '\n</head>\n<body>\n' + body + '\n</body>\n</html>\n')
out = os.path.join(HERE, "index.html")
open(out, "w", encoding="utf-8").write(doc)
print("gerado:", out, "(", len(doc), "bytes )  -> copie para apuracao-sp/index.html")
