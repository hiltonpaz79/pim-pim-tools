"""
Divisor de PDF em imagens - arraste um ou mais PDFs para cima do programa.

- Cada página do PDF vira uma imagem (já comprimida, leve para o dia a dia)
- Cada PDF gera a sua própria pasta, ao lado dele:
      aula1.pdf  ->  aula1_dividido_em_imagens\\
                         aula1_pag_01.jpg
                         aula1_pag_02.jpg
                         ...
- Arrastar vários PDFs gera uma pasta para cada um
- Arrastar uma pasta processa todos os PDFs que houver dentro dela
- O PDF original nunca é alterado

Requisitos: pip install pypdfium2 pillow
"""
import re
import sys
from pathlib import Path

import pypdfium2 as pdfium

# --- Ajustes -----------------------------------------------------------------
DPI = 150            # 150 = ótimo para tela, slides e impressão comum.
                     # 100 = mais leve | 200-300 = mais nítido e mais pesado
IMG_FORMAT = "jpg"   # "jpg" = mais leve | "png" = sem perda (maior), bom p/ texto
JPEG_QUALITY = 85    # 80-90 é a faixa usual
MAX_SIDE_PX = 8000   # trava de segurança para páginas gigantes (pôsteres)
# -----------------------------------------------------------------------------

SUFFIX = "_dividido_em_imagens"


def natural_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def unique_dir(p: Path) -> Path:
    if not p.exists():
        return p
    n = 1
    while True:
        q = p.with_name(f"{p.name}_{n}")
        if not q.exists():
            return q
        n += 1


def collect(paths):
    found = []
    for p in map(Path, paths):
        if p.is_dir():
            for f in p.rglob("*"):
                if (f.is_file() and f.suffix.lower() == ".pdf"
                        and not any(part.endswith(SUFFIX) for part in f.parts)):
                    found.append(f)
        elif p.is_file() and p.suffix.lower() == ".pdf":
            found.append(p)
    return sorted(set(found), key=natural_key)


def save_image(img, out: Path):
    if IMG_FORMAT.lower() == "png":
        img.save(out, format="PNG", optimize=True, dpi=(DPI, DPI))
    else:
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True,
                 dpi=(DPI, DPI))


def split_pdf(src: Path):
    """Divide um PDF. Retorna (pasta, páginas_ok, páginas_com_erro)."""
    try:
        pdf = pdfium.PdfDocument(str(src))
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg:
            raise ValueError("PDF protegido por senha")
        raise ValueError(f"não consegui abrir o PDF ({e})")

    try:
        total = len(pdf)
        if total == 0:
            raise ValueError("o PDF não tem páginas")

        out_dir = unique_dir(src.parent / f"{src.stem}{SUFFIX}")
        out_dir.mkdir(parents=True)
        digits = max(2, len(str(total)))
        ext = "png" if IMG_FORMAT.lower() == "png" else "jpg"

        ok = failed = 0
        for i in range(total):
            print(f"   página {i + 1}/{total}...", end="\r", flush=True)
            try:
                page = pdf[i]
                w, h = page.get_size()  # em pontos (1/72 polegada)
                scale = DPI / 72
                if max(w, h) * scale > MAX_SIDE_PX:
                    scale = MAX_SIDE_PX / max(w, h)
                img = page.render(scale=scale).to_pil().convert("RGB")
                page.close()
                save_image(img, out_dir / f"{src.stem}_pag_{i + 1:0{digits}d}.{ext}")
                ok += 1
            except Exception as e:
                failed += 1
                print(f"   ! página {i + 1}: {e}" + " " * 20)

        if ok == 0:
            try:
                out_dir.rmdir()
            except OSError:
                pass
            raise ValueError("nenhuma página pôde ser convertida")
        return out_dir, ok, failed
    finally:
        pdf.close()


def folder_size_mb(folder: Path) -> float:
    return sum(f.stat().st_size for f in folder.iterdir() if f.is_file()) / 1024 / 1024


def main():
    pdfs = collect(sys.argv[1:])
    if not pdfs:
        print("Arraste um ou mais PDFs (ou uma pasta com PDFs) para este programa.")
        input("\nEnter para sair...")
        return

    total_pdfs = total_pages = 0
    for src in pdfs:
        print(f"{src.name}")
        try:
            out_dir, ok, failed = split_pdf(src)
            print(f"   OK: {ok} imagem(ns), {folder_size_mb(out_dir):.1f} MB "
                  f"-> {out_dir.name}" + " " * 20)
            if failed:
                print(f"   ! {failed} página(s) com erro")
            total_pdfs += 1
            total_pages += ok
        except Exception as e:
            print(f"   ERRO: {e}" + " " * 20)
        print()

    print(f"Concluído: {total_pdfs} PDF(s), {total_pages} página(s) convertida(s).")
    input("\nEnter para fechar...")


if __name__ == "__main__":
    main()
