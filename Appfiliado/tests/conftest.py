import sys
from pathlib import Path

# Os modulos do bot (parser.py, formatador.py, afiliados.py etc.) sao
# importados de forma "achatada" (sem pacote), entao garantimos que a
# pasta do app esteja no sys.path independente de onde o pytest for
# chamado (ex: da raiz do monorepo ou de dentro de Appfiliado/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
