# AI-Based Environmental Health Advisory and Intelligent Air Quality Monitoring System

A modular, deterministic-first air quality monitoring, predictive analytics, and environmental health advisory application built with **Python**, **Streamlit**, **SQLite**, **scikit-learn**, **FAISS**, and **Groq**.

---

## Key Features

* **Live Telemetry & Station Monitoring**: Connects to the World Air Quality Index (WAQI) API with station search, preloaded Delhi monitoring station dropdowns, direct feed ID (`@uid`) lookups, and graceful failure handling.
* **Telemetry Validation Gate**: Validates incoming sensor payloads for missing pollutants (preserved as `None`, never zero-imputed), non-finite or negative values, coordinate integrity, and observation timestamp freshness.
* **Deterministic CPCB IND-AQI Engine**: Computes individual pollutant sub-indices (`PM2.5`, `PM10`, `NO2`, `SO2`, `CO`, `O3`), determines overall AQI (`max` sub-index), identifies the dominant AQI-contributing pollutant, and classifies air quality into six CPCB severity tiers (*Good*, *Satisfactory*, *Moderate*, *Poor*, *Very Poor*, *Severe*).
* **Pollutant & Non-Causal Source Intelligence**: Distinguishes highest raw concentration from dominant sub-index impact, detects multi-pollutant combination signatures, and generates evidence-graded source associations without claiming causation.
* **Rule-Based Health & Activity Advisors**: Provides general and sensitive-group public-health precautions alongside activity suitability guidance (*Walking*, *Running*, *Cycling*, *Outdoor exercise*, *Indoor exercise*) with explicit non-diagnostic disclaimers.
* **SQLite Persistence & Historical Analytics**: Stores deduplicated observations across 6 normalized SQLite tables (`stations`, `aqi_observations`, `pollutant_measurements`, `pollutant_analyses`, `health_advisories`, `alerts`) and computes daily/weekly rollups, severity distributions, and timestamp-aware multi-station comparisons.
* **MLP Next-Observation Severity Prediction**: Trains and evaluates a chronological `MLPClassifier` (`scikit-learn`) on historical pollutant sequences (with optional `t-1` lag features) to predict next-observation severity with confidence scores and evaluation metrics (Accuracy, Precision, Recall, F1, Confusion Matrix).
* **Explainable Statistical Anomaly Detection**: Flags sudden AQI step jumps, historical z-score deviations, and unusual pollutant shifts while accounting for missing data, irregular intervals, and invalid measurements.
* **Independent Meteorological & Spatial Context**: Integrates Open-Meteo weather telemetry (temperature, humidity, wind speed/direction, rainfall, surface pressure) independently of WAQI and maps real station coordinates for hotspot screening.
* **In-App Smart Alerts**: Evaluates AQI thresholds, deterioration deltas, pollutant limits, and statistical anomalies with SQLite deduplication and acknowledgement tracking.
* **RAG Knowledge Base & Groq AI Assistant**: Indexes curated environmental and public-health reference documents in a persisted **FAISS** vector store (`TF-IDF` + `TruncatedSVD`), routes queries across 10 deterministic intents, and synthesizes grounded explanations via **Groq** (`llama-3.3-70b-versatile`) with automatic deterministic fallback when offline or unconfigured.
* **Environmental Reports & Data Quality Diagnostics**: Generates Daily, Weekly, and Monthly summaries with **ReportLab PDF** and **Pandas CSV** exports alongside a Data Quality & System Health dashboard.

---

## Architecture & Project Structure

The system enforces a **deterministic-first architecture**: all AQI calculations, rule evaluations, anomaly detection, and ML predictions run in validated Python modules outside the LLM, while the assistant strictly explains verified system outputs and retrieved RAG passages.

```text
air_quality_advisory/
├── app.py                              # Multi-page Streamlit entry point & navigation
├── config.py                           # Environment & path configuration loader
├── requirements.txt                    # Python dependencies
├── .env.example                        # Credential template
├── .gitignore                          # Git exclusion rules (.env, *.db, caches)
├── assets/
│   └── styles.css                      # Custom clean UI styling
├── data/
│   ├── aqi_monitoring.db               # Auto-initialized SQLite database
│   ├── mlp_aqi_severity_model.joblib   # Persisted MLP model artifact
│   ├── knowledge_base/                 # Curated environmental & health Markdown docs
│   └── rag_index/                      # Persisted FAISS index & metadata
├── pages/
│   ├── 01_overview.py                  # Integrated system overview dashboard
│   ├── 02_live_aqi_monitoring.py       # Live WAQI station search & ingestion
│   ├── 03_pollutant_intelligence.py    # Sub-index breakdown & source insights
│   ├── 04_health_advisory.py           # Profile-based health guidance
│   ├── 05_ai_environmental_assistant.py# RAG + Groq conversational assistant
│   ├── 06_aqi_prediction.py            # MLP training, evaluation & next-step prediction
│   ├── 07_anomaly_detection.py         # Statistical anomaly history & step deltas
│   ├── 08_historical_analytics.py      # Time-series, severity & daily/weekly rollups
│   ├── 09_location_comparison.py       # Multi-station comparison with timestamp checks
│   ├── 10_geographic_monitoring.py     # Coordinate map & hotspot screening
│   ├── 11_weather_analysis.py          # Open-Meteo weather & dispersion context
│   ├── 12_smart_alerts.py              # Deduplicated in-app alerts & acknowledgement
│   ├── 13_activity_advisor.py          # Activity-specific suitability advisor
│   ├── 14_environmental_reports.py     # Daily/Weekly/Monthly PDF & CSV reports
│   └── 15_data_quality.py              # Completeness, accuracy & subsystem health
├── src/
│   ├── activity/                       # Activity suitability rules
│   ├── alerts/                         # Alert evaluation, deduplication & storage
│   ├── analytics/                      # Historical rollups, comparison & PDF/CSV reports
│   ├── api/                            # WAQI and Open-Meteo API clients
│   ├── chatbot/                        # 10-intent router & Groq response generator
│   ├── core/                           # CPCB AQI engine & health advisory rules
│   ├── database/                       # SQLite connection, schema & repository
│   ├── intelligence/                   # Pollutant analysis, source insights & anomalies
│   ├── prediction/                     # MLP preprocessing, training, evaluation & inference
│   ├── rag/                            # Document chunking, embeddings, FAISS & retrieval
│   ├── utils/                          # Shared Streamlit UI components
│   └── validation/                     # Telemetry validation & staleness checks
└── tests/                              # Pytest unit & end-to-end QA test suite
