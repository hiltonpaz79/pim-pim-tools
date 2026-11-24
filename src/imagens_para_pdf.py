"""
Imagens e PDFs -> um único PDF. Arraste arquivos para cima do programa.

Arquivos soltos (imagens e/ou PDFs):
- 1 imagem            -> PDF com o mesmo nome, ao lado da imagem
- Vários arquivos     -> UM único PDF, unindo tudo em ordem alfabética dos
                         nomes (ordem "natural": arq2 vem antes de arq10)
- Só PDFs             -> também são unidos em um único PDF
- Imagens e PDFs      -> misturados no mesmo PDF, na ordem dos nomes

Qualidade preservada:
- Cada página de imagem tem exatamente o tamanho da imagem (sem bordas)
- JPEG e PNG entram no PDF sem recompressão
- As páginas dos PDFs são copiadas como estão

Pastas arrastadas: a pasta e cada subpasta que tenha imagens viram um PDF
próprio, com o nome da pasta, salvo ao lado dela.
(Dentro de pastas, só as imagens são consideradas, não os PDFs.)

Formatos de imagem: JPG, PNG, WEBP, BMP, GIF, TIFF

Requisitos: pip install img2pdf pypdf pillow
"""
import io
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import img2pdf
from pypdf import PdfReader, PdfWriter
from pypdf.errors import DeprecationError

logging.getLogger("img2pdf").setLevel(logging.ERROR)  # esconde avisos técnicos

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
PDF_EXT = ".pdf"

# Define o tamanho físico das páginas de imagem (pixels -> polegadas). Só muda
# o tamanho da página ao imprimir; a imagem em si nunca é alterada.
PAGE_DPI = 96


def natural_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def is_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMG_EXTS


def is_pdf(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() == PDF_EXT


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    n = 1
    while True:
        q = p.with_name(f"{p.stem}_{n}{p.suffix}")
        if not q.exists():
            return q
        n += 1


def image_to_pdf_bytes(images) -> bytes:
    layout = img2pdf.get_fixed_dpi_layout_fun((PAGE_DPI, PAGE_DPI))
    return img2pdf.convert([str(i) for i in images], layout_fun=layout)


def folder_jobs(root: Path):
    """Um PDF para a pasta e para cada subpasta que tenha imagens."""
    subdirs = sorted((p for p in root.rglob("*") if p.is_dir()),
                     key=lambda p: [natural_key(Path(x)) for x in p.relative_to(root).parts])
    for d in [root] + subdirs:
        try:
            imgs = sorted((f for f in d.iterdir() if is_image(f)), key=natural_key)
        except OSError:
            continue
        if imgs:
            name = d.name or "Imagens"
            yield imgs, unique_path(d.parent / f"{name}.pdf")


def build_images_pdf(images, out: Path):
    out.write_bytes(image_to_pdf_bytes(images))


def merge_files(files, out: Path):
    """Une imagens e PDFs, na ordem dada, em um único PDF. Retorna (ok, falhas)."""
    writer = PdfWriter()
    failures = []
    for f in files:
        try:
            if is_pdf(f):
                reader = PdfReader(str(f))
                if reader.is_encrypted and not reader.decrypt(""):
                    raise ValueError("PDF protegido por senha")
            else:
                reader = PdfReader(io.BytesIO(image_to_pdf_bytes([f])))
            try:
                writer.append(reader, outline_item=f.stem)  # um marcador por arquivo
            except (TypeError, DeprecationError):
                writer.append(reader)  # versões do pypdf sem esse parâmetro
        except Exception as e:
            failures.append((f, e))
    if len(writer.pages) == 0:
        raise ValueError("nenhum arquivo pôde ser lido")
    with open(out, "wb") as fh:
        writer.write(fh)
    return len(writer.pages), failures


def main():
    args = [Path(a) for a in sys.argv[1:]]

    if not args:
        print("Arraste imagens e/ou PDFs, ou uma pasta, para cima deste programa.")
        input("\nEnter para sair...")
        return

    loose = sorted((a for a in args if is_image(a) or is_pdf(a)), key=natural_key)
    folders = [a for a in args if a.is_dir()]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Cada job: (descrição, arquivos, destino, função)
    jobs = []
    if loose:
        has_pdf = any(is_pdf(f) for f in loose)
        if len(loose) == 1 and has_pdf:
            print(f"{loose[0].name}: só há um PDF, nada para unir.")
            print("Arraste pelo menos dois arquivos para uni-los.\n")
        elif len(loose) == 1:
            jobs.append((loose, unique_path(loose[0].with_suffix(".pdf")), "img"))
        elif has_pdf:
            out = loose[0].parent / f"Unido_{stamp}.pdf"
            jobs.append((loose, unique_path(out), "merge"))
        else:
            out = loose[0].parent / f"Imagens_{stamp}.pdf"
            jobs.append((loose, unique_path(out), "img"))
    for d in folders:
        for imgs, out in folder_jobs(d):
            jobs.append((imgs, out, "img"))

    if not jobs:
        if not loose:
            print("Nenhum arquivo compatível encontrado.")
        input("\nEnter para sair...")
        return

    for files, out, kind in jobs:
        try:
            if kind == "merge":
                pages, failures = merge_files(files, out)
            else:
                build_images_pdf(files, out)
                pages, failures = len(files), []
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"OK: {out.name}  ({pages} página(s), {size_mb:.2f} MB)")
            for i, f in enumerate(files, 1):
                tag = "PDF" if is_pdf(f) else "IMG"
                print(f"   {i:>3}. [{tag}] {f.name}")
            for f, e in failures:
                print(f"   ! ignorado: {f.name} ({e})")
        except Exception as e:
            print(f"ERRO ao gerar {out.name}: {e}")
        print()

    input("Enter para fechar...")


if __name__ == "__main__":
    main()
