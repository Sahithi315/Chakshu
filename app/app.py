"""Doctor screen. Run from the repo root:  streamlit run app/app.py"""
import glob, hashlib, html, json, os, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
import streamlit as st
from src.reports.extract import extract_pdf, highlight, quote_check
from src.symptoms.infer import Extractor

MODEL_DIR = f"{ROOT}/models/modernbert_f100_s1"  # declared main model; fixed, not chosen by any score
PDF_DIR = f"{ROOT}/data/synthetic_lab_reports"
DECISIONS = f"{ROOT}/data/decisions.json"
KINDS = {"SYMPTOM": "Symptom", "NEG_SYMPTOM": "Denied symptom", "DURATION": "Duration", "SEVERITY": "Severity"}
COLORS = {"SYMPTOM": "#ffe08a", "NEG_SYMPTOM": "#ffb3b3", "DURATION": "#b9dcff", "SEVERITY": "#d9c2ff"}
STATES = {"confirmed": "Doctor confirmed", "corrected": "Corrected", "rejected": "Rejected"}

st.set_page_config(page_title="Doctor brief", layout="wide")
st.warning("Prototype. Synthetic data only. Not for clinical use.")
st.title("Doctor brief")


# ---- saved decisions (local JSON; the original value is written once and never overwritten) ----
def load_decisions():
    try:
        return json.load(open(DECISIONS))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        st.error(f"{DECISIONS} cannot be read. Fix or move it; nothing was changed.")
        st.stop()


def save_decision(item, state, corrected=None):
    d = load_decisions()
    rec = d.setdefault(item["id"], {"original": item["original"], "context": item["context"], "history": []})
    rec["state"] = state
    if corrected is not None:
        rec["corrected_value"] = corrected
    rec["history"].append({"state": state, "corrected_value": corrected, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    os.makedirs(os.path.dirname(DECISIONS), exist_ok=True)
    json.dump(d, open(DECISIONS + ".tmp", "w"), indent=1)
    os.replace(DECISIONS + ".tmp", DECISIONS)
    st.session_state.editing = None


def item_id(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


# ---- models and extraction (cached) ----
@st.cache_resource(show_spinner="Loading symptom model...")
def get_model():
    return Extractor(MODEL_DIR)


@st.cache_data(show_spinner="Reading PDF...")
def read_pdf(path):
    return extract_pdf(path)


@st.cache_data(show_spinner=False)
def page_image(path, page, bbox):
    return highlight(path, page, bbox)


# ---- one item = one row with provenance, state and the three buttons ----
def show_item(item, decisions):
    rec = decisions.get(item["id"])
    state = STATES.get(rec["state"], "Unreviewed") if rec else "Unreviewed"
    st.markdown(f"**{item['title']}**  \n{item['detail']}")
    st.caption(" · ".join(item["sources"]) + f" · State: **{state}**")
    if rec and rec.get("corrected_value"):
        c = rec["corrected_value"]
        st.caption(f"Original: {item['original_text']} → Corrected: {c['text']}" + ("" if c.get("quote_ok", True) else " (corrected value not found in its source line)"))
    a, b, c, d = st.columns(4)
    k = item["id"]
    a.button("Show source", key=f"src{k}", on_click=st.session_state.update, kwargs={"selected": item})
    b.button("Confirm", key=f"ok{k}", on_click=save_decision, args=(item, "confirmed"))
    c.button("Correct", key=f"fix{k}", on_click=st.session_state.update, kwargs={"editing": k})
    d.button("Reject", key=f"no{k}", on_click=save_decision, args=(item, "rejected"))
    if st.session_state.get("editing") == k:
        with st.form(f"form{k}"):
            kind = st.selectbox("Type", list(KINDS.values()), index=list(KINDS.values()).index(item["kind"])) if item["part"] == "symptom" else None
            text = st.text_input("Corrected value", value=item["original_text"])
            if st.form_submit_button("Save correction"):
                quote_ok = quote_check(text, item["source_line"]) if item["part"] == "lab" else True
                save_decision(item, "corrected", {"text": text, "kind": kind, "quote_ok": quote_ok})
                st.rerun()
    st.divider()


def symptom_items(text, spans):
    out = []
    for s in spans:
        phrase = text[s["start"]:s["end"]]
        kind = KINDS[s["label"]]
        out.append({"id": item_id("sym", text, s["start"], s["end"], s["label"]), "part": "symptom", "title": f"{kind}: {phrase}",
                    "detail": "", "kind": kind, "label": s["label"], "span": (s["start"], s["end"]), "text": text,
                    "original_text": phrase, "source_line": text,
                    "sources": ["Typed by patient", "Model output, needs doctor confirmation"], "context": {"typed_text": text},
                    "original": {"kind": kind, "text": phrase, "start": s["start"], "end": s["end"]}})
    return out


def lab_items(path, name, key):
    out = []
    for r in read_pdf(path):
        note = f" · {r['range_note']}" if r["range_note"] else ""
        flag = "" if r["quote_ok"] else " · value not found in its source line"
        out.append({"id": item_id("lab", key, r["page"], r["test"], [round(x) for x in r["bbox"]]), "part": "lab", "title": r["test"],
                    "detail": f"{r['value']} {r['unit']} · printed range {r['reference_range']}{note}{flag}", "kind": "Lab result",
                    "path": path, "page": r["page"], "bbox": tuple(r["bbox"]), "original_text": r["value"], "source_line": r["source_line"],
                    "sources": ["Extracted from uploaded document"], "context": {"file": name, "page": r["page"], "source_line": r["source_line"]},
                    "original": {k: r[k] for k in ("test", "value", "unit", "reference_range", "range_note", "page", "bbox")}})
    return out


def show_source(item):
    st.subheader("Source")
    if item["part"] == "lab":
        st.caption(f"{item['context']['file']} · page {item['page']} · {item['source_line']}")
        st.image(page_image(item["path"], item["page"], item["bbox"]), width="stretch")
    else:
        t, (s, e) = item["text"], item["span"]
        st.markdown(f"<div style='font-size:1.1rem'>{html.escape(t[:s])}<mark style='background:{COLORS[item['label']]}'>{html.escape(t[s:e])}</mark>{html.escape(t[e:])}</div>", unsafe_allow_html=True)
        st.caption("Typed by patient")


left, right = st.columns([3, 2])
decisions = load_decisions()
with left:
    st.header("Symptoms")
    st.caption("Typed by the patient. Tags below are model output and need doctor confirmation.")
    text = st.text_area("Patient text (English)", key="typed", height=100, placeholder="no fever but cough for 3 days, mild headache")
    if st.button("Tag symptoms") and text.strip():
        if len(text.split()) > 90:
            st.warning("Long text: the model reads the start of long messages (about 128 tokens).")
        if not text.isascii():
            st.warning("This model was trained on English text. Other scripts give unreliable tags.")
        spans = get_model().spans([text])[0]
        st.session_state.sym = {"text": text, "spans": spans}
    if "sym" in st.session_state:
        t, sp = st.session_state.sym["text"], st.session_state.sym["spans"]
        marked, pos = "", 0
        for s in sp:
            marked += html.escape(t[pos:s["start"]]) + f"<mark style='background:{COLORS[s['label']]}'>{html.escape(t[s['start']:s['end']])}</mark><sup>{KINDS[s['label']]}</sup>"
            pos = s["end"]
        st.markdown(f"<div style='font-size:1.1rem;line-height:1.8'>{marked + html.escape(t[pos:])}</div>", unsafe_allow_html=True)
        items = symptom_items(t, sp)
        if not items:
            st.info("No tagged phrases in this text.")
        for it in items:
            show_item(it, decisions)

    st.header("Lab report")
    st.caption("Extracted from the document by plain code; values are copied from the page.")
    files = sorted(glob.glob(f"{PDF_DIR}/*.pdf"))
    pick = st.selectbox("Synthetic report", [os.path.basename(f) for f in files])
    up = st.file_uploader("Or upload a PDF", type="pdf")
    path, name = f"{PDF_DIR}/{pick}", pick
    if up is not None:
        data = up.getvalue()
        name = up.name
        path = os.path.join(tempfile.gettempdir(), f"ccp_{hashlib.sha1(data).hexdigest()[:10]}.pdf")
        open(path, "wb").write(data)
    try:
        items = lab_items(path, name, name if up is None else path)
    except Exception as e:  # unreadable or unusual PDF: say so, do not guess
        items = []
        st.error(f"Could not read this PDF: {type(e).__name__}: {e}")
    if not items and up is not None:
        st.info("No result rows were found in this PDF.")
    for it in items:
        show_item(it, decisions)

with right:
    if st.session_state.get("selected"):
        show_source(st.session_state.selected)
    else:
        st.subheader("Source")
        st.caption("Choose Show source on an item.")
