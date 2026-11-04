"""PDF -> pages -> overlapping word-window chunks, each tagged with product and page for citation."""
import json
import logging
import re
from pathlib import Path

from pypdf import PdfReader

from . import config

logging.getLogger("pypdf").setLevel(logging.ERROR)


PRODUCT_NAMES = {
    "AIAAnnuityFix_EN.pdf": "AIA Annuity Fix",
    "AIACICare_EN_20Aug19.pdf": "AIA CI Care",
    "AIACITopUp_EN_21Aug19.pdf": "AIA CI Top Up",
    "AIAEndowment15Pay25_ENversion_20200409.pdf": "AIA Endowment 15/25 (Non-Par)",
    "AIASeniorHappy_Brochure_EN_20201209.pdf": "AIA Senior Happy",
    "AIA_10_15PayLife_EN_nov19_2_20200102.pdf": "AIA 10/15 Pay Life (Non-Par)",
    "AIA_Excellent_NonPar_Brochure2022_EN.pdf": "AIA Excellent (Non-Par)",
    "AIA_HS_new_standard_EN_06102021.pdf": "AIA H&S (new standard)",
    "AIA_Health_Happy_EN_Brochure_Sep2021.pdf": "AIA Health Happy",
    "AIA_Issara_Plus_FEB2022_En.pdf": "AIA Issara Plus",
    "AIA_Issara_Prestige_Plus_FEB2022_En.pdf": "AIA Issara Prestige Plus",
    "AIA_Smart_Select_FEB2022_En.pdf": "AIA Smart Select",
    "AIA_Smart_Wealth_FEB2022_En.pdf": "AIA Smart Wealth",
    "Brochure_AIA_Infinite_Gift_Prestige_EN_20210830.pdf": "AIA Infinite Gift Prestige",
    "EN_Prestige_Dec_2020_R.pdf": "AIA Infinite Wealth Prestige (Unit Linked)",
    "Term5_10_15_20_EN_20181029.pdf": "AIA Term 5/10/15/20",
}


def product_name(filename: str) -> str:
    return PRODUCT_NAMES.get(filename, Path(filename).stem.replace("_", " "))


def is_english(text: str, min_ratio: float = 0.85) -> bool:
    """Some brochures named *_EN are Thai-language; their text extracts as garbage. Keep English pages only."""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) >= min_ratio


def clean(text: str) -> str:
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_pages(raw_dir: Path = config.RAW_DIR) -> list[dict]:
    pages = []
    for pdf in sorted(raw_dir.glob("*.pdf")):
        reader = PdfReader(str(pdf))
        for i, page in enumerate(reader.pages, start=1):
            text = clean(page.extract_text() or "")
            if text and is_english(text):
                pages.append({"doc": pdf.name, "product": product_name(pdf.name), "page": i, "text": text})
    return pages


def chunk_page(page: dict, words: int, overlap: int) -> list[dict]:
    toks = page["text"].split()
    step = max(1, words - overlap)
    out = []
    for start in range(0, max(1, len(toks)), step):
        window = toks[start:start + words]
        if not window:
            break
        out.append({
            "doc": page["doc"], "product": page["product"], "page": page["page"],
            "text": " ".join(window),
        })
        if start + words >= len(toks):
            break
    return out


def build_chunks(pages: list[dict], words: int = config.CHUNK_WORDS, overlap: int = config.CHUNK_OVERLAP) -> list[dict]:
    chunks = []
    for p in pages:
        for c in chunk_page(p, words, overlap):
            c["id"] = len(chunks)
            chunks.append(c)
    return chunks


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    pages = extract_pages()
    write_jsonl(config.PAGES_PATH, pages)
    chunks = build_chunks(pages)
    write_jsonl(config.CHUNKS_PATH, chunks)
    print(f"{len({p['doc'] for p in pages})} docs, {len(pages)} pages, {len(chunks)} chunks")


if __name__ == "__main__":
    main()
