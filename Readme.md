# AIChE Abstract Analysis: Keyword & Geo-Extraction Pipeline

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
