# AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System

An end-to-end, deterministic-first air quality monitoring, predictive analytics, and environmental health advisory platform built with **Python**, **Streamlit**, **SQLite**, **scikit-learn**, **FAISS**, and **Groq**.

---

## About the Project

**AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System** is a multi-page analytical web application that turns raw air quality telemetry, historical station records, meteorological context, and curated public-health knowledge into clear, actionable environmental guidance.

Rather than relying on an LLM to calculate air quality scores or guess missing values, the system separates **deterministic calculations and data validation** from **machine learning forecasts** and **retrieval-grounded AI explanations**.

---

## What Problem It Solves

Raw air quality data and public-health guidance often create friction for everyday users and analysts:

1. **Raw Numbers Without Context**: Seeing an AQI value or pollutant concentration (`PM2.5`, `PM10`, `NO2`, `SO2`, `CO`, `O3`) alone does not immediately tell people which pollutant is driving risk, how sensitive groups are affected, or whether outdoor exercise is sensible.
2. **Incomplete or Stale Telemetry**: Live monitoring feeds can have missing pollutants, delayed timestamps, or invalid readings. Treating missing fields as zero or mixing stale readings with fresh ones skews analysis and comparisons.
3. **Unreliable or Unverified AI Answers**: Purely generative answers can hallucinate thresholds, fabricate missing readings, or offer medical diagnoses instead of grounding responses in actual measurements and trusted reference material.
4. **Fragmented Tracking & Reporting**: Monitoring live conditions, reviewing historical trends, spotting unusual spikes, checking weather/station maps, and exporting summaries often live in disconnected tools.

---

## What Solution It Provides

The application brings these workflows together in one modular Streamlit platform across **15 integrated pages**:

* **Deterministic CPCB AQI & Pollutant Intelligence**: Validates incoming telemetry (keeping missing pollutants as `None` rather than inventing zeros), computes CPCB-aligned pollutant sub-indices and overall AQI, identifies the dominant AQI contributor vs. highest raw pollutant, and highlights multi-pollutant combinations and non-causal source associations.
* **Health & Activity Advisory Engines**: Tailors public-health precautions (general vs. sensitive groups) and activity guidance (*Walking*, *Running*, *Cycling*, *Outdoor exercise*, *Indoor exercise*) with clear non-diagnostic and non-guarantee notices.
* **Persistent SQLite Storage & Analytics**: Deduplicates observations across normalized SQLite tables and powers time-series charts, severity distributions, daily/weekly rollups, and timestamp-aware location comparisons.
* **Next-Step MLP Severity Prediction & Anomaly Detection**: Trains a chronological `MLPClassifier` on historical sequences (with optional `t-1` lag features) to predict next-observation severity with evaluation metrics, alongside explainable statistical anomaly detection for sudden jumps and baseline deviations.
* **Weather, Map & Smart Alerts**: Integrates Open-Meteo weather data independently of WAQI, plots stations with real coordinates for hotspot screening, and persists deduplicated in-app alerts with acknowledgement support.
* **FAISS RAG + Groq Assistant**: Retrieves relevant passages from a persisted FAISS knowledge index (`TF-IDF` + `TruncatedSVD`), routes questions across 10 deterministic intents, and generates grounded explanations using Groq (`llama-3.3-70b-versatile`) with automatic deterministic fallback when offline or unconfigured.
* **PDF & CSV Reports + Data Quality View**: Generates Daily, Weekly, and Monthly summaries (with insufficient-data guards), exports **ReportLab PDF** and **Pandas CSV** files, and surfaces completeness vs. accuracy and subsystem availability.

---

## Project Structure

```text
air_quality_advisory/
├── app.py                              # Main Streamlit entry point & navigation
├── config.py                           # Environment & path configuration
├── requirements.txt                    # Python dependencies
├── .env.example                        # Template for environment variables
├── .gitignore                          # Excludes .env, SQLite DBs, and caches
├── assets/
│   └── styles.css                      # UI styling
├── data/
│   ├── aqi_monitoring.db               # SQLite database (auto-created)
│   ├── mlp_aqi_severity_model.joblib   # Saved MLP model artifact (after training)
│   ├── knowledge_base/                 # Curated environmental & health Markdown docs
│   └── rag_index/                      # Persisted FAISS index & metadata
├── pages/
│   ├── 01_overview.py
│   ├── 02_live_aqi_monitoring.py
   ├── 03_pollutant_intelligence.py
   ├── 04_health_advisory.py
   ├── 05_ai_environmental_assistant.py
   ├── 06_aqi_prediction.py
   ├── 07_anomaly_detection.py
   ├── 08_historical_analytics.py
   ├── 09_location_comparison.py
   ├── 10_geographic_monitoring.py
   ├── 11_weather_analysis.py
   ├── 12_smart_alerts.py
   ├── 13_activity_advisor.py
   ├── 14_environmental_reports.py
   └── 15_data_quality.py
├── src/
│   ├── activity/
│   ├── alerts/
│   ├── analytics/
│   ├── api/
│   ├── chatbot/
│   ├── core/
│   ├── database/
│   ├── intelligence/
│   ├── prediction/
│   ├── rag/
│   ├── utils/
│   └── validation/
└── tests/
