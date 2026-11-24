"""
Base64 to Image - arraste arquivos .txt com Base64 para cima do programa.

- Aceita Base64 puro ou "data:image/...;base64,...."
- Detecta o formato sozinho (PNG, JPG, GIF, WEBP, BMP, ICO, TIFF, SVG)
- Salva em uma pasta "imagens" ao lado do arquivo, com o mesmo nome
- Sem arrastar nada (duplo clique): converte o Base64 da área de transferência
  e salva em "imagens" ao lado do programa

Não precisa instalar nenhuma biblioteca.
"""
import base64
import binascii
import re
import sys
from datetime import datetime
from pathlib import Path

OUT_NAME = "imagens"


def detect_ext(data: bytes):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith(b"\x00\x00\x01\x00"):
        return ".ico"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tif"
    head = data[:300].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:1000].lower()):
        return ".svg"
    return None


def decode_base64(text: str) -> bytes:
    text = text.strip().strip('"').strip("'")
    # remove prefixo data URI
    m = re.match(r"^data:[^;,]*(;[^,]*)?,", text, re.IGNORECASE)
    if m:
        text = text[m.end():]
    # remove espaços e quebras de linha
    text = re.sub(r"\s+", "", text)
    # aceita Base64 "URL safe"
    text = text.replace("-", "+").replace("_", "/")
    # corrige padding ausente
    text += "=" * (-len(text) % 4)
    try:
        return base64.b64decode(text, validate=True)
    except binascii.Error:
        raise ValueError("o texto não é um Base64 válido")


def unique_path(folder: Path, stem: str, ext: str) -> Path:
    p = folder / f"{stem}{ext}"
    n = 1
    while p.exists():
        p = folder / f"{stem}_{n}{ext}"
        n += 1
    return p


def convert_text(text: str, folder: Path, stem: str) -> Path:
    data = decode_base64(text)
    ext = detect_ext(data)
    if ext is None:
        raise ValueError("o conteúdo foi decodificado, mas não é uma imagem reconhecida")
    folder.mkdir(parents=True, exist_ok=True)
    out = unique_path(folder, stem, ext)
    out.write_bytes(data)
    return out


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("latin-1", errors="ignore")


def app_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def from_clipboard():
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        text = root.clipboard_get()
        root.destroy()
    except Exception:
        print("Não consegui ler a área de transferência (ou ela está vazia).")
        return
    stem = "clipboard_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        out = convert_text(text, app_folder() / OUT_NAME, stem)
        print(f"OK: {out}")
    except (binascii.Error, ValueError) as e:
        print(f"ERRO: {e}")


def main():
    files = [Path(a) for a in sys.argv[1:] if Path(a).is_file()]

    if not files:
        print("Nenhum arquivo arrastado. Usando a área de transferência...\n")
        from_clipboard()
        input("\nEnter para fechar...")
        return

    ok = 0
    for f in files:
        try:
            out = convert_text(read_text_file(f), f.parent / OUT_NAME, f.stem)
            print(f"{f.name} -> {OUT_NAME}\\{out.name}")
            ok += 1
        except (binascii.Error, ValueError) as e:
            print(f"ERRO em {f.name}: {e}")
        except Exception as e:
            print(f"ERRO em {f.name}: {e}")

    print(f"\n{ok} de {len(files)} convertido(s).")
    input("\nEnter para fechar...")


if __name__ == "__main__":
    main()
