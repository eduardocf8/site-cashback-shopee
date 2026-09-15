"""A rolagem do carrossel já renderizada como vídeo de fundo transparente.

Alternativa aos quadros-chave no editor: em vez de animar a Posição X da tira na mão,
o movimento sai pronto num arquivo. Na edição é só arrastar para a linha do tempo por
cima da cena - não tem quadro-chave, escala nem posição para acertar.

O que se perde é o controle fino do tempo: a duração e a curva ficam decididas aqui.
Para mudar, altere as constantes de tempo abaixo e rode de novo.

A janela de 1080x1920 caminha por cima da tira com desaceleração cúbica (ease-out):
começa rápido e vai freando até parar no card da marca, que é como um carrossel de
celular se comporta depois do peteleco. Quadro-chave linear no editor dá velocidade
constante, que lê como esteira.

O enquadramento é o mesmo do card solto - mesma altura, mesma posição - então cortar
do card para este vídeo no momento da rolagem não move nada na tela.

Dois formatos, porque o suporte a transparência varia de editor para editor:

- WebM (VP9 com alfa): leve, uns 500 KB. É o primeiro a tentar.
- MOV (PNG com alfa): sem perda e aceito por praticamente tudo, mas pesado - por isso
  sai a 30 quadros por segundo, enquanto o WebM sai a 60.

Nenhum dos dois é "fundo verde": o alfa de verdade preserva a sombra do cartão, que
um recorte por croma comeria junto com o fundo.

Como usar:
    python3 gerar_cards_produto.py     # gera a tira, se ainda não existir
    python3 gerar_rolagem_video.py
"""
import subprocess
from pathlib import Path

from gerar_cards_produto import (
    ALTURA,
    LARGURA,
    LARGURA_CARTAO,
    MARGEM_LATERAL,
    PRODUTOS,
    VAO,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parent / "cards-produto"

# O quadro do reel. A largura é a mesma do card (LARGURA), então a tira entra em 1x,
# pixel a pixel - é o que dispensa qualquer ajuste de escala no editor.
ALTURA_QUADRO = 1920

# Tempos, em segundos. A espera no começo e no fim existe para dar margem de corte:
# sem elas, o primeiro e o último quadro do arquivo já seriam movimento.
ESPERA_INICIO = 0.3
DURACAO_ROLAGEM = 1.4
ESPERA_FIM = 0.3

TIRAS = {
    "carrossel-tira-1x.png": "rolagem-carrossel",
    "carrossel-tira-marca-clara-1x.png": "rolagem-carrossel-marca-clara",
    "carrossel-tira-marca-em-card-1x.png": "rolagem-carrossel-marca-em-card",
}


def _ffmpeg() -> str:
    """O container não traz ffmpeg no PATH, e o que vem junto do Playwright é uma
    compilação mínima (VP8, sem os filtros que este script usa). O binário do
    imageio-ffmpeg é completo; se houver um ffmpeg no sistema, ele vem primeiro."""
    from shutil import which

    caminho = which("ffmpeg")
    if caminho:
        return caminho
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _expressao_da_janela() -> str:
    """Posição X da janela sobre a tira, quadro a quadro.

    O percurso é o mesmo que os quadros-chave fariam: um passo de card por produto,
    do primeiro até o card da marca. Sai daqui em vez de ser um número escrito na mão
    para acompanhar a lista de produtos sem ninguém precisar refazer a conta.
    """
    percurso = len(PRODUTOS) * (LARGURA_CARTAO + VAO)
    # clip(...) segura a janela parada antes de começar e depois de chegar; o (1-p)^3
    # é a desaceleração.
    p = f"clip((t-{ESPERA_INICIO})/{DURACAO_ROLAGEM}\\,0\\,1)"
    return f"{percurso}*(1-pow(1-{p}\\,3))"


def _renderizar(tira: Path, destino: Path, fps: int, argumentos_codec: list[str]):
    y = (ALTURA_QUADRO - ALTURA) // 2
    filtros = (
        f"crop={LARGURA}:{ALTURA}:x='{_expressao_da_janela()}':y=0,"
        f"pad={LARGURA}:{ALTURA_QUADRO}:0:{y}:color=0x00000000"
    )
    comando = [
        _ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(fps), "-i", str(tira),
        "-filter_complex", filtros + "," + argumentos_codec[0],
        "-t", str(ESPERA_INICIO + DURACAO_ROLAGEM + ESPERA_FIM),
        *argumentos_codec[1:], str(destino),
    ]
    subprocess.run(comando, check=True)
    mb = destino.stat().st_size / 1048576
    print(f"gerado: {destino.relative_to(REPO_ROOT)} ({fps} qps, {mb:.1f} MB)")


def gerar():
    if not (OUT_DIR / "carrossel-tira-1x.png").exists():
        raise SystemExit("Rode gerar_cards_produto.py antes - a tira 1x não existe ainda.")

    for arquivo, base in TIRAS.items():
        tira = OUT_DIR / arquivo
        if not tira.exists():
            continue
        _renderizar(
            tira, OUT_DIR / f"{base}.webm", 60,
            ["format=yuva420p", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
             "-b:v", "0", "-crf", "26", "-auto-alt-ref", "0"],
        )

    # O MOV sai só da versão padrão: é o plano B para um editor que recuse o WebM, e
    # cada arquivo desses pesa umas cinquenta vezes mais que o WebM equivalente.
    _renderizar(
        OUT_DIR / "carrossel-tira-1x.png", OUT_DIR / "rolagem-carrossel.mov", 30,
        ["format=rgba", "-c:v", "png"],
    )

    percurso = len(PRODUTOS) * (LARGURA_CARTAO + VAO)
    print(
        f"\nJanela de {LARGURA}x{ALTURA_QUADRO}, percorrendo {percurso} px em "
        f"{DURACAO_ROLAGEM}s, com {ESPERA_INICIO}s parada no primeiro card e "
        f"{ESPERA_FIM}s parada na marca."
    )


if __name__ == "__main__":
    gerar()
