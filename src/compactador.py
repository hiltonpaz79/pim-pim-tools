"""
TinyCompress v2 - arraste imagens (ou pastas) para cima do programa.

- PNG  : usa pngquant (mesmo motor do TinyPNG). Se o pngquant.exe não for
         encontrado, usa o Pillow como alternativa (qualidade menor).
- JPEG : recompressão otimizada e progressiva.
- WEBP : recompressão.
- PDF  : recomprime as imagens JPEG de dentro do PDF (mesma qualidade do JPG),
         recompacta o conteúdo sem perda e remove objetos duplicados.
         Imagens sem perda (PNG) dentro do PDF não são alteradas.

Saída (originais nunca são alterados, nomes são mantidos):
- Arquivo arrastado -> pasta "comprimidas" ao lado do arquivo
- Pasta arrastada   -> pasta "<nome>_comprimidas" ao lado dela,
                       com a mesma estrutura de subpastas

Requisitos: pip install pillow pypdf
Opcional (qualidade TinyPNG): colocar pngquant.exe na mesma pasta do script/EXE
"""
import io
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image
from pypdf import PdfReader, PdfWriter

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
OUT_NAME = "comprimidas"

# --- Ajustes de qualidade ---------------------------------------------------
# Níveis tentados em ordem. O último ("0-100") nunca recusa: usa até 256 cores
# com o melhor dithering, igual ao TinyPNG.
PNG_QUALITY_STEPS = ["90-100", "70-100", "0-100"]
PNG_SPEED = "1"          # 1 = melhor qualidade (mais lento) ... 11 = mais rápido
JPEG_QUALITY = 80
WEBP_QUALITY = 80
# ---------------------------------------------------------------------------


def find_pngquant():
    """Procura pngquant.exe junto do programa, embutido no EXE ou no PATH."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", "")) / "pngquant.exe")
        candidates.append(Path(sys.executable).parent / "pngquant.exe")
    else:
        candidates.append(Path(__file__).parent / "pngquant.exe")
    for c in candidates:
        if c.is_file():
            return str(c)
    return shutil.which("pngquant")


PNGQUANT = find_pngquant()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def png_pngquant(src: Path, dst: Path) -> bool:
    for q in PNG_QUALITY_STEPS:
        r = subprocess.run(
            [PNGQUANT, "--quality", q, "--speed", PNG_SPEED,
             "--floyd=1", "--strip", "--force", "--output", str(dst), "--", str(src)],
            capture_output=True, creationflags=NO_WINDOW,
        )
        if r.returncode == 0 and dst.exists():
            return True
    return False


def png_pillow(src: Path, dst: Path):
    img = Image.open(src)
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        q = img.convert("RGBA").quantize(colors=256, method=Image.Quantize.FASTOCTREE)
    else:
        q = img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    q.save(dst, format="PNG", optimize=True)


def shrink_pdf_image(img):
    """Recomprime só imagens JPEG do PDF; as sem perda ficam como estão."""
    if not img.name.lower().endswith((".jpg", ".jpeg")):
        return
    try:
        pil = img.image
        if pil.mode not in ("RGB", "L"):
            return
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        if buf.tell() < len(img.data) * 0.95:  # só troca se valer a pena
            img.replace(pil, quality=JPEG_QUALITY, optimize=True)
    except Exception:
        return


def compress_pdf(src: Path, dst: Path):
    reader = PdfReader(str(src))
    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("PDF protegido por senha")
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        try:
            for img in page.images:
                shrink_pdf_image(img)
        except Exception:
            pass
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
    try:
        # Sem argumentos: o nome dos parâmetros muda entre versões do pypdf.
        writer.compress_identical_objects()
    except Exception:
        pass  # é só uma otimização extra; o PDF continua válido sem ela
    with open(dst, "wb") as fh:
        writer.write(fh)


def compress(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()

    if ext == ".png":
        ok = False
        if PNGQUANT:
            ok = png_pngquant(src, dst)  # falha (código 99) se não atingir a qualidade mínima
        else:
            png_pillow(src, dst)
            ok = True
        if not ok:
            shutil.copy2(src, dst)  # não dá para comprimir sem perda visível
    elif ext in (".jpg", ".jpeg"):
        Image.open(src).convert("RGB").save(
            dst, format="JPEG", quality=JPEG_QUALITY,
            optimize=True, progressive=True, subsampling="4:2:0",
        )
    elif ext == ".webp":
        Image.open(src).save(dst, format="WEBP", quality=WEBP_QUALITY, method=6)
    elif ext == ".pdf":
        compress_pdf(src, dst)

    # Se ficou maior que o original, mantém o original
    if dst.stat().st_size >= src.stat().st_size:
        shutil.copy2(src, dst)


def is_output_path(p: Path) -> bool:
    return any(part == OUT_NAME or part.endswith("_" + OUT_NAME) for part in p.parts)


def collect(paths):
    """Gera pares (arquivo_origem, arquivo_destino)."""
    for p in map(Path, paths):
        if p.is_dir():
            out_root = p.parent / f"{p.name}_{OUT_NAME}"
            for f in p.rglob("*"):
                if f.suffix.lower() in EXTS and not is_output_path(f.relative_to(p)):
                    yield f, out_root / f.relative_to(p)
        elif p.suffix.lower() in EXTS:
            yield p, p.parent / OUT_NAME / p.name


def main():
    jobs = list(collect(sys.argv[1:]))
    if not jobs:
        print("Arraste imagens PNG/JPG/WEBP (ou pastas) para este programa.")
        input("Enter para sair...")
        return

    print("Motor PNG:", "pngquant" if PNGQUANT else "Pillow (pngquant.exe não encontrado)")
    print()

    total_before = total_after = 0
    for src, dst in jobs:
        try:
            compress(src, dst)
            before, after = src.stat().st_size, dst.stat().st_size
            total_before += before
            total_after += after
            print(f"{src.name}: {before/1024:.0f} KB -> {after/1024:.0f} KB "
                  f"({100 - after*100/before:.0f}% menor)")
        except Exception as e:
            print(f"ERRO em {src.name}: {e}")

    if total_before:
        print(f"\nTotal: {total_before/1024:.0f} KB -> {total_after/1024:.0f} KB "
              f"({100 - total_after*100/total_before:.0f}% de economia)")
    input("\nEnter para fechar...")


if __name__ == "__main__":
    main()
