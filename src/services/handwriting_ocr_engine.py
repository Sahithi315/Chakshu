"""Multi-engine handwriting-aware OCR module for CareVision.

Combines:
1. Microsoft TrOCR (VisionEncoderDecoderModel fine-tuned on cursive handwriting) — local offline weights.
2. Windows Native Neural OCR (WinRT Windows.Media.Ocr) — local OS neural OCR for printed/mixed regions.
3. Tesseract 5.5 LSTM — complementary pass with illumination-normalized ink and de-slanting.

Provides batch line recognition, genuine token/word-level confidence scoring, cross-engine consensus,
and strict readability validation to prevent corrupted OCR text from entering clinical fields.
"""
from pathlib import Path
import difflib
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
import pytesseract

ROOT = Path(__file__).resolve().parent.parent.parent
LOCAL_TROCR_DIR = ROOT / "models" / "trocr_base_handwritten"

_trocr_processor = None
_trocr_model = None
_trocr_load_attempted = False
_win_ocr_available: Optional[bool] = None


def is_trocr_available() -> bool:
    """Return True if local TrOCR handwriting model weights are available on disk."""
    if os.environ.get("CAREVISION_DISABLE_TROCR", "").lower() in ("1", "true", "yes"):
        return False
    return LOCAL_TROCR_DIR.is_dir() and (LOCAL_TROCR_DIR / "config.json").exists()


def _load_trocr():
    """Lazily load local offline TrOCR processor and model once per process."""
    global _trocr_processor, _trocr_model, _trocr_load_attempted
    if _trocr_load_attempted:
        return _trocr_processor, _trocr_model
    _trocr_load_attempted = True
    if not is_trocr_available():
        return None, None
    try:
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        _trocr_processor = TrOCRProcessor.from_pretrained(str(LOCAL_TROCR_DIR), local_files_only=True)
        _trocr_model = VisionEncoderDecoderModel.from_pretrained(str(LOCAL_TROCR_DIR), local_files_only=True)
        _trocr_model.eval()
        # Keep CPU threading well-utilized without oversubscription
        torch.set_num_threads(min(8, max(2, os.cpu_count() or 4)))
    except Exception:
        _trocr_processor = None
        _trocr_model = None
    return _trocr_processor, _trocr_model


def _prepare_crop_for_trocr(crop: np.ndarray) -> Image.Image:
    """Convert a grayscale/BGR line crop to clean padded RGB PIL image for TrOCR ViT encoder."""
    if len(crop.shape) == 2:
        rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    # TrOCR expects horizontal single-line crops with clean white margins
    pad_y = max(12, int(h * 0.18))
    pad_x = max(16, int(w * 0.04))
    padded = cv2.copyMakeBorder(rgb, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return Image.fromarray(padded)


def recognize_lines_trocr(crops: List[np.ndarray], batch_size: int = 8, max_new_tokens: int = 24) -> Optional[List[Tuple[str, float]]]:
    """
    Run batch TrOCR handwriting inference on a list of cropped line images.

    Returns:
        List of (decoded_text, confidence_0_to_100) matching `crops`, or None if TrOCR is unavailable.
    """
    if not crops:
        return []
    processor, model = _load_trocr()
    if processor is None or model is None:
        return None

    try:
        import torch

        results: List[Tuple[str, float]] = []
        pil_images = [_prepare_crop_for_trocr(c) for c in crops]

        for start in range(0, len(pil_images), batch_size):
            batch_imgs = pil_images[start : start + batch_size]
            pixel_values = processor(images=batch_imgs, return_tensors="pt").pixel_values
            with torch.no_grad():
                outputs = model.generate(
                    pixel_values,
                    max_new_tokens=max_new_tokens,
                    return_dict_in_generate=True,
                    output_scores=True,
                    num_beams=1,
                )
            sequences = outputs.sequences
            texts = processor.batch_decode(sequences, skip_special_tokens=True)

            # Compute genuine per-sequence confidence from token softmax probabilities
            step_probs = []
            for step_logits in outputs.scores:
                probs = torch.softmax(step_logits, dim=-1)
                max_p, _ = probs.max(dim=-1)
                step_probs.append(max_p.cpu().numpy())

            for idx, txt in enumerate(texts):
                clean_txt = re.sub(r"\s+", " ", (txt or "")).strip()
                # Collect probabilities for non-pad/non-eos tokens of this sequence
                seq_tokens = sequences[idx].cpu().tolist()
                eos_id = getattr(model.config, "eos_token_id", 2)
                pad_id = getattr(model.config, "pad_token_id", 1)
                tok_ps = []
                for step_i, p_arr in enumerate(step_probs):
                    tok_pos = step_i + 1  # sequences[0] is decoder_start_token_id
                    if tok_pos < len(seq_tokens):
                        tok_id = seq_tokens[tok_pos]
                        if tok_id in (eos_id, pad_id):
                            break
                        tok_ps.append(float(p_arr[idx]))
                conf = (sum(tok_ps) / len(tok_ps) * 100.0) if tok_ps else 0.0
                # Discount confidence if decoded text is suspiciously empty or purely punctuation
                if not any(ch.isalnum() for ch in clean_txt):
                    conf = min(conf, 15.0)
                results.append((clean_txt, round(conf, 1)))

        return results
    except Exception:
        return None


def is_windows_ocr_available() -> bool:
    """Check if local Windows native WinRT neural OCR is available."""
    global _win_ocr_available
    if _win_ocr_available is not None:
        return _win_ocr_available
    if sys.platform != "win32":
        _win_ocr_available = False
        return False
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]; "
                "([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages).Count",
            ],
            capture_output=True, text=True, timeout=5
        )
        _win_ocr_available = proc.returncode == 0 and int((proc.stdout or "0").strip() or "0") > 0
    except Exception:
        _win_ocr_available = False
    return _win_ocr_available


def run_windows_ocr_on_image(image_path_or_bgr) -> List[str]:
    """
    Run local Windows native neural OCR (WinRT Windows.Media.Ocr) on a full document image.
    Returns list of recognized lines (especially clean on printed headers, dates, and mixed docs).
    """
    if not is_windows_ocr_available():
        return []
    tmp_path = None
    try:
        if isinstance(image_path_or_bgr, (str, Path)):
            img_path = str(Path(image_path_or_bgr).resolve())
        else:
            fd, tmp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            cv2.imwrite(tmp_path, image_path_or_bgr)
            img_path = tmp_path

        ps_script = (
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
            "$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]; "
            "$null = [Windows.Storage.Streams.DataWriter, Windows.Storage.Streams, ContentType=WindowsRuntime]; "
            "$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]; "
            "$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]; "
            "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { "
            "$_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
            "function Await($t, $rt) { $nt = $asTaskGeneric.MakeGenericMethod($rt).Invoke($null, @($t)); $nt.Wait(-1) | Out-Null; return $nt.Result }; "
            "$bytes = [System.IO.File]::ReadAllBytes($args[0]); "
            "$ms = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream; "
            "$w = New-Object Windows.Storage.Streams.DataWriter($ms.GetOutputStreamAt(0)); "
            "$w.WriteBytes($bytes); $null = Await ($w.StoreAsync()) ([uint32]); $ms.Seek(0); "
            "$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ms)) ([Windows.Graphics.Imaging.BitmapDecoder]); "
            "$bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap]); "
            "$eng = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); "
            "$res = Await ($eng.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult]); "
            "foreach ($ln in $res.Lines) { Write-Output $ln.Text }; $ms.Dispose()"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script, img_path],
            capture_output=True, text=True, timeout=12
        )
        if proc.returncode == 0 and proc.stdout:
            return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    except Exception:
        pass
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
    return []


def _deslant_gray(img: np.ndarray, shear: float = -0.18) -> np.ndarray:
    """Apply subtle horizontal shear correction to normalize italic/cursive handwriting slant."""
    h, w = img.shape[:2]
    m = np.float32([[1.0, shear, -shear * h / 2.0], [0.0, 1.0, 0.0]])
    return cv2.warpAffine(img, m, (w, h), borderValue=255)


def recognize_line_tesseract(gray_crop: np.ndarray) -> Dict[str, Any]:
    """Run clean padded Tesseract LSTM pass on a single line crop with conditional de-slanted fallback."""
    gh, gw = gray_crop.shape[:2]
    if gh < 6 or gw < 8:
        return {"text": "", "alt_texts": [], "confidence": 0.0, "words": []}

    scale = min(2.2, 80.0 / float(max(1, gh))) if gh < 72 else 1.0
    scaled = cv2.resize(gray_crop, (int(gw * scale), int(gh * scale)), interpolation=cv2.INTER_CUBIC) if scale > 1.08 else gray_crop
    padded = cv2.copyMakeBorder(scaled, 22, 22, 28, 28, cv2.BORDER_CONSTANT, value=255)

    def _run_pass(img_arr: np.ndarray, psm: int) -> Tuple[str, float, List[Tuple[str, float]]]:
        try:
            data = pytesseract.image_to_data(img_arr, config=f"--oem 1 --psm {psm}", output_type=pytesseract.Output.DICT)
            words = []
            confs = []
            for t, c in zip(data["text"], data["conf"]):
                tok = (t or "").strip()
                cf = float(c)
                if tok and cf >= 0:
                    words.append((tok, cf))
                    confs.append(cf)
            txt = " ".join(w[0] for w in words).strip()
            avg_c = sum(confs) / len(confs) if confs else 0.0
            return txt, avg_c, words
        except Exception:
            return "", 0.0, []

    best_txt, best_conf, best_words = _run_pass(padded, 7)
    alt_texts = [best_txt] if best_txt else []

    def _quality(t: str, c: float) -> float:
        alnum = sum(1 for ch in t if ch.isalnum())
        alpha = sum(1 for ch in t if ch.isalpha())
        noise = sum(1 for ch in t if ch in "~`|\\^_@#§°«»")
        return alpha * 2.0 + alnum * 0.8 + c * 0.45 - noise * 2.5

    best_q = _quality(best_txt, best_conf)
    if best_conf < 65.0 or len(best_txt) < 4:
        dsl = _deslant_gray(padded, -0.18)
        for img_var, psm in [(padded, 6), (dsl, 7), (padded, 8)]:
            t, c, w_list = _run_pass(img_var, psm)
            if t and t not in alt_texts:
                alt_texts.append(t)
            q = _quality(t, c)
            if q > best_q:
                best_q = q
                best_txt, best_conf, best_words = t, c, w_list

    return {
        "text": best_txt,
        "alt_texts": alt_texts,
        "confidence": round(best_conf, 1),
        "words": best_words,
    }


def _text_readability_score(text: str, conf: float) -> float:
    """Heuristic readability score (0..100) rewarding clean alphabetic words and penalizing OCR gibberish."""
    t = (text or "").strip()
    if not t:
        return 0.0
    non_space = [ch for ch in t if not ch.isspace()]
    if not non_space:
        return 0.0
    alnum = sum(1 for ch in non_space if ch.isalnum())
    noise = sum(1 for ch in non_space if ch in "~`|\\^_@#§°«»{}")
    alnum_ratio = alnum / float(len(non_space))
    noise_ratio = noise / float(len(non_space))

    tokens = re.findall(r"[A-Za-z0-9\-\./%]+", t)
    good_words = 0
    for tok in tokens:
        if tok.isdigit() or re.match(r"^\d+[\-\./]\d+", tok):
            good_words += 1
        elif len(tok) >= 3 and tok.isalpha():
            # Penalize consonant-only or random mixed-case OCR garbage like 'PNME' / 'eLMrabs'
            has_vowel = any(v in tok.lower() for v in "aeiouy")
            weird_caps = sum(1 for ch in tok[1:] if ch.isupper()) > 0 and not tok.isupper()
            if has_vowel and not weird_caps:
                good_words += 1

    word_ratio = good_words / float(max(1, len(tokens)))
    score = (conf * 0.45) + (alnum_ratio * 25.0) + (word_ratio * 30.0) - (noise_ratio * 45.0)
    return max(0.0, min(100.0, round(score, 1)))


def is_readable_clinical_text(text: str, confidence: float = 0.0, min_score: float = 54.0) -> bool:
    """
    Strict anti-gibberish gate: returns True only if text looks genuinely readable
    rather than corrupted OCR characters. Prevents random OCR text from entering clinical UI.
    """
    t = (text or "").strip()
    if len(t) < 3:
        return False
    if "\ufffd" in t or "\x00" in t:
        return False
    non_space = [ch for ch in t if not ch.isspace()]
    if not non_space:
        return False
    alnum_ratio = sum(1 for ch in non_space if ch.isalnum()) / float(len(non_space))
    if alnum_ratio < 0.62:
        return False
    if confidence > 0 and confidence < 45.0:
        return False
    return _text_readability_score(t, confidence) >= min_score


def recognize_handwritten_lines(
    gray_crops: List[np.ndarray],
    bgr_crops: Optional[List[np.ndarray]] = None,
    prefer_trocr: bool = True,
) -> List[Dict[str, Any]]:
    """
    Multi-engine handwriting-aware OCR for a batch of segmented line crops.
    Runs local TrOCR (when weights are present) + Tesseract LSTM, fuses results with genuine
    confidence scoring, and returns rich per-line metadata.
    """
    if not gray_crops:
        return []

    # 1. Run fast Tesseract LSTM pass on all crops first
    tess_results = [recognize_line_tesseract(gc) for gc in gray_crops]

    # 2. Run local TrOCR batch ONLY on handwritten / low-confidence lines (keeps CPU latency crisp!)
    trocr_map: Dict[int, Tuple[str, float]] = {}
    if prefer_trocr and is_trocr_available():
        trocr_indices = [
            i for i, tr in enumerate(tess_results)
            if float(tr["confidence"]) < 78.0 or not is_readable_clinical_text(tr["text"], float(tr["confidence"]))
        ]
        if trocr_indices:
            src_list = bgr_crops if (bgr_crops and len(bgr_crops) == len(gray_crops)) else gray_crops
            tr_crops = [src_list[i] for i in trocr_indices]
            tr_out = recognize_lines_trocr(tr_crops, batch_size=8, max_new_tokens=24)
            if tr_out is not None:
                for idx_pos, orig_i in enumerate(trocr_indices):
                    if idx_pos < len(tr_out):
                        trocr_map[orig_i] = tr_out[idx_pos]

    fused: List[Dict[str, Any]] = []
    for idx, tess in enumerate(tess_results):
        tess_txt = tess["text"]
        tess_conf = float(tess["confidence"])

        trocr_txt, trocr_conf = trocr_map.get(idx, ("", 0.0))

        alt_texts: List[str] = []
        for cand in [trocr_txt, tess_txt] + tess.get("alt_texts", []):
            if cand and cand not in alt_texts:
                alt_texts.append(cand)

        agree = (
            difflib.SequenceMatcher(None, trocr_txt.lower(), tess_txt.lower()).ratio()
            if (trocr_txt and tess_txt) else 0.0
        )

        if trocr_txt:
            trocr_q = _text_readability_score(trocr_txt, trocr_conf)
            tess_q = _text_readability_score(tess_txt, tess_conf)
            if tess_conf >= 82.0 and tess_q > trocr_q + 8.0:
                best_txt = tess_txt
                best_conf = tess_conf
                engine_used = "tesseract+trocr"
            else:
                best_txt = trocr_txt
                if agree >= 0.72:
                    best_conf = min(96.0, max(trocr_conf, tess_conf) + 5.0)
                elif agree >= 0.45:
                    best_conf = trocr_conf
                else:
                    # Discount confidence when engines disagree to avoid trusting language-model hallucinations
                    best_conf = min(trocr_conf, 58.0)
                engine_used = "trocr+tesseract"
        else:
            best_txt = tess_txt
            best_conf = tess_conf
            engine_used = "tesseract"

        fused.append({
            "text": best_txt,
            "trocr_text": trocr_txt,
            "trocr_confidence": round(trocr_conf, 1),
            "tesseract_text": tess_txt,
            "tesseract_confidence": round(tess_conf, 1),
            "engine_agreement": round(agree, 3),
            "alt_texts": alt_texts,
            "confidence": round(best_conf, 1),
            "readability_score": _text_readability_score(best_txt, best_conf),
            "is_readable": is_readable_clinical_text(best_txt, best_conf),
            "engine": engine_used,
            "words": tess.get("words", []),
        })

    return fused
