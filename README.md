# AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System

An end-to-end, deterministic-first air quality monitoring, predictive analytics, and environmental health advisory platform built with **Python**, **Streamlit**, **SQLite**, **scikit-learn**, **FAISS**, and **Groq**.

---

## About the Project

**AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System** is a multi-page analytical web application that transforms raw air quality telemetry, historical station records, meteorological context, and curated public-health knowledge into clear, actionable environmental guidance.

Rather than relying on an LLM to calculate air quality scores or guess missing values, the system separates **deterministic calculations and data validation** from **machine learning forecasts** and **retrieval-grounded AI explanations**.

---

## Key Features & Architecture

The platform integrates **15 modular Streamlit pages** backed by a normalized local storage layer and deterministic engines:

- **Deterministic CPCB AQI & Pollutant Intelligence**: Validates incoming telemetry (preserving missing pollutants as `None` rather than inventing zeros), computes CPCB-aligned pollutant sub-indices and overall AQI, distinguishes the dominant AQI contributor from the highest raw pollutant, and flags multi-pollutant combinations alongside non-causal source associations.
- **Health & Activity Advisory Engines**: Generates risk-stratified precautions (general population vs. sensitive groups) and activity guidance (*Walking*, *Running*, *Cycling*, *Outdoor exercise*, *Indoor exercise*) with clear non-diagnostic disclaimers.
- **Persistent SQLite Storage & Analytics**: Deduplicates observations across normalized SQLite tables (`aqi_monitoring.db`) to power time-series charts, severity distributions, daily/weekly rollups, and timestamp-aware location comparisons.
- **Next-Step MLP Severity Prediction & Anomaly Detection**: Trains a chronological `MLPClassifier` on historical sequences (with optional `t-1` lag features) to predict next-observation severity with full evaluation metrics, paired with explainable statistical anomaly detection for sudden spikes and baseline deviations.
- **Weather, Geographic Mapping & Smart Alerts**: Integrates Open-Meteo meteorological data independently of WAQI, plots stations with verified coordinates for hotspot screening, and persists deduplicated in-app alerts with acknowledgement tracking.
- **FAISS RAG + Groq Assistant**: Retrieves relevant context from a persisted FAISS knowledge index (`TF-IDF` + `TruncatedSVD`), routes queries across 10 deterministic intents, and generates grounded explanations via Groq (`llama-3.3-70b-versatile`) with automatic deterministic fallback when offline or unconfigured.
- **PDF & CSV Reporting + Data Quality Auditing**: Compiles Daily, Weekly, and Monthly summaries (with insufficient-data guards), exports **ReportLab PDF** and **Pandas CSV** reports, and tracks telemetry completeness and subsystem health.

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
│   └── styles.css                      # Custom UI styling
├── data/
│   ├── aqi_monitoring.db               # SQLite database (auto-created)
│   ├── mlp_aqi_severity_model.joblib   # Saved MLP model artifact (after training)
│   ├── knowledge_base/                 # Curated environmental & health Markdown docs
│   └── rag_index/                      # Persisted FAISS index & metadata
├── pages/
│   ├── 01_overview.py                  # Executive dashboard & current status
│   ├── 02_live_aqi_monitoring.py       # Real-time WAQI ingestion & validation
│   ├── 03_pollutant_intelligence.py    # Sub-index breakdown & source context
│   ├── 04_health_advisory.py           # General & sensitive-group health guidance
│   ├── 05_ai_environmental_assistant.py# RAG + Groq grounded Q&A interface
│   ├── 06_aqi_prediction.py            # Chronological MLP training & forecasting
│   ├── 07_anomaly_detection.py         # Statistical spike & deviation detection
│   ├── 08_historical_analytics.py      # Long-term trends & severity rollups
│   ├── 09_location_comparison.py       # Multi-station timestamp-aware comparison
│   ├── 10_geographic_monitoring.py     # Geospatial station map & hotspot view
│   ├── 11_weather_analysis.py          # Open-Meteo meteorological correlation
│   ├── 12_smart_alerts.py              # Deduplicated threshold & spike alerts
│   ├── 13_activity_advisor.py          # Outdoor/indoor physical activity guidance
│   ├── 14_environmental_reports.py     # PDF & CSV report generation
│   └── 15_data_quality.py              # Completeness metrics & system diagnostics
├── src/
│   ├── activity/                       # Activity suitability rules
│   ├── alerts/                         # Alert generation & persistence
│   ├── analytics/                      # Historical aggregations & comparisons
│   ├── api/                            # WAQI & Open-Meteo API clients
│   ├── chatbot/                        # Intent routing & Groq LLM integration
│   ├── core/                           # CPCB AQI engine & domain constants
│   ├── database/                       # SQLite schema, connection & CRUD
│   ├── intelligence/                   # Multi-pollutant & source association logic
│   ├── prediction/                     # MLP model pipeline & anomaly detectors
│   ├── rag/                            # FAISS index builder & retriever
│   ├── utils/                          # Formatting, PDF/CSV export & helpers
│   └── validation/                     # Telemetry sanitization & quality checks
└── tests/                              # Automated unit & integration test suite
