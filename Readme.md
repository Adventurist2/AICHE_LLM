# AIChE Abstract Analysis: Keyword & Geo-Extraction Pipeline

## Current application and datasets

The current pipeline is organized into `01_scraping/`, `02_extraction/`,
`03_grouping/`, `04_clustering/`, and `05_webapp/`. Raw papers, extraction outputs,
aggregated keywords, clustering snapshots, prepared web indices, historical
archives, and validation reports are included. See [context/current.md](context/current.md)
for the current implementation and [05_webapp/README.md](05_webapp/README.md)
for application methods, validation, and limitations. The roadmap below describes
the earlier experiments.

### Clone and run

Install Python 3.12 and Git LFS, then run in PowerShell:

```powershell
git lfs install
git clone --branch chandan https://github.com/Adventurist2/AICHE_LLM.git
cd AICHE_LLM
git lfs pull
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\05_webapp\requirements.txt
& .\.venv\Scripts\python.exe -m streamlit run .\05_webapp\app.py
```

Open http://localhost:8501. The five pages are Explorer, Trends, Geography,
Institutes, and About & metrics. The prepared indices allow the app to start
without rebuilding the Ward tree. Semantic search may download its embedding
model on first use. API credentials are only needed for the extraction services;
keep them in a local `.env` file, which is excluded from Git.

Large aggregate JSON files and NumPy arrays use Git LFS. A source ZIP or a clone
without LFS downloads contains pointer files in their place. Local environments,
model caches, editor state, and credentials are excluded; the code and datasets
are retained.

### Snapshot status at upload (November 6, 2026)

The installed explorer snapshot contains 173,438 keywords and 313,858 mentions
at five clustering heights. The newer frozen input contains 183,489 keywords
and 331,849 mentions, with partial 2017 extraction coverage, under
`reports/keyword_refresh_2026-11-04/`. Its Ward rebuild stopped on November 4
before producing a completed new tree. The failure status and inputs are
preserved; the newer twelve-height results are not installed. See the saved
`refresh_status.json` files for the status of each run.

## 1. Project Overview

This repository contains an end-to-end pipeline designed to automate the extraction of high-value technical keywords and author metadata from chemical engineering research abstracts. The primary objective is to move beyond generic academic terminology (e.g., "results," "methodology") to identify specific domain concepts (e.g., "ionic liquids," "metal-organic frameworks") and visualize global research trends.

## 2. Technical Roadmap

The project documentation tracks three distinct technical strategies, reflecting an evolution from local hardware optimization to scalable cloud integration:

### Phase I: Local Inference with `llama.ipynb`

Focuses on "squeezing" Large Language Models onto consumer-grade hardware.

* **Tech Stack:** `transformers`, `torch`, `bitsandbytes`.
* **Strategy:** Implements **8-bit quantization** (`llm_int8_enable_fp32_cpu_offload`) to allow models like **Mistral-7B** and **Zephyr-7B** to run on limited VRAM by offloading specific layers to the system RAM.
* **Geospatial Analysis:** Uses `geopy` (Nominatim) for geocoding affiliations and `Plotly Express` for interactive world map visualizations.

### Phase II: Optimized Local Serving with `ollama.ipynb`

Transitioned to a more robust local serving layer for higher throughput.

* **Tech Stack:** `ollama-python`.
* **Strategy:** Leverages the **Llama 3** model via the Ollama backend to handle concurrent extraction requests.
* **Prompt Engineering:** Uses structured **System Prompts** and **Few-Shot** learning examples to force the LLM into a strict JSON output schema.

### Phase III: Production Cloud Pipeline with `open_router.ipynb`

Designed for processing the full conference dataset (584+ abstracts) with high reliability.

* **Tech Stack:** `OpenRouter API`, `python-dotenv`.
* **Strategy:** Switches to a cloud gateway to access **Mistral-7B-Instruct** without hardware limitations.
* **Resilience:** Implements a **3-attempt retry loop** and **Regex-based JSON "hunting"** to ensure data recovery even during API instability or malformed model responses.

## 3. Core Features & Logic

* **Blacklist Filtering:** A sophisticated `GENERIC` list removes over 50+ common academic filler words.
* **Contextual Whitelisting:** A `KEEP_IF_CONTAINS` list prevents the accidental removal of technical phrases that contain generic words (e.g., keeping "Analysis of catalysts").
* **Batch Compilation:** Automatically scans directories of individual JSON abstracts and merges them into a unified `all_combined_extracted.json`.

## 4. Project Structure

```text
├── llama.ipynb           # Experiments with quantization & mapping
├── ollama.ipynb          # Local Llama 3 extraction logic
├── open_router.ipynb     # Production script for batch processing
├── .env                  # API Key management (not included in repo)
├── data/                 # Raw AIChE abstract JSON files
└── output/               # Extracted results & consolidated master file

```

## 5. Requirements & Setup

* **Python Environment:** Python 3.10+
* **Dependencies:** `pip install transformers ollama openai pandas plotly geopy python-dotenv`
* **Configuration:** Create a `.env` file in the root directory and add your key: `OPENROUTER_API_KEY=your_key_here`

---

## Current Working File
- Working in file llama file on openrouter
- THen would work on groq trying to use api keys and do multiple things
