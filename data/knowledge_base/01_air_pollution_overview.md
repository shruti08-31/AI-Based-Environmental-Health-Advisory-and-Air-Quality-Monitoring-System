# Ambient Air Pollution & CPCB National Air Quality Index Overview
Source: CPCB National Air Quality Index (IND-AQI) & WHO Air Quality Overview

Ambient air pollution consists of complex mixtures of suspended particulate matter and reactive gases emitted from combustion, industrial processes, construction dust, agricultural burning, and secondary atmospheric reactions. The Central Pollution Control Board (CPCB) National Air Quality Index classifies air quality into six standardized categories: Good (0-50), Satisfactory (51-100), Moderate (101-200), Poor (201-300), Very Poor (301-400), and Severe (401-500). Overall AQI is governed by the highest individual pollutant sub-index rather than an average across pollutants.

---

## 1. Tracked Criteria Pollutants & Averaging Windows
The CPCB IND-AQI evaluates air quality across eight major criteria pollutants, each assigned a specific averaging period to reflect acute versus chronic exposure risks:

* **Particulate Matter ($PM_{10}$ and $PM_{2.5}$):** Inhalable particles ($\le 10\,\mu\text{m}$) and fine respirable particles ($\le 2.5\,\mu\text{m}$), evaluated over a **24-hour** average.
* **Nitrogen Dioxide ($NO_2$):** A reddish-brown reactive gas primarily generated from vehicular exhaust and power generation, evaluated over a **24-hour** average.
* **Sulfur Dioxide ($SO_2$):** A pungent gas emitted mainly by fossil fuel combustion (coal/oil) and industrial smelting, evaluated over a **24-hour** average.
* **Ground-Level Ozone ($O_3$):** A secondary pollutant formed when nitrogen oxides ($NO_x$) and volatile organic compounds (VOCs) react in sunlight, evaluated over an **8-hour** rolling average.
* **Carbon Monoxide ($CO$):** A colorless, odorless gas produced by incomplete combustion of carbon-based fuels, evaluated over an **8-hour** rolling average (measured in $\text{mg/m}^3$).
* **Ammonia ($NH_3$):** An alkaline gas largely originating from agricultural fertilizers, livestock waste, and industrial refrigeration, evaluated over a **24-hour** average.
* **Lead ($Pb$):** A toxic heavy metal emitted from metal processing, battery manufacturing, and waste incineration, evaluated over a **24-hour** average.

---

## 2. CPCB AQI Breakpoint Matrix & Minimum Data Rules
To compute a valid CPCB AQI at any monitoring station, concentrations must meet strict data-sufficiency criteria:
1. **Minimum Pollutant Rule:** Valid sub-indices must be available for at least **three pollutants**.
2. **Particulate Mandate:** At least one of those three measured pollutants must be **$PM_{2.5}$ or $PM_{10}$**.
3. **Temporal Sufficiency:** At least **16 hours** of valid monitoring data are required to compute a 24-hour sub-index.

| AQI Category (Range) | $PM_{10}$ (24-hr, $\mu\text{g/m}^3$) | $PM_{2.5}$ (24-hr, $\mu\text{g/m}^3$) | $NO_2$ (24-hr, $\mu\text{g/m}^3$) | $O_3$ (8-hr, $\mu\text{g/m}^3$) | $CO$ (8-hr, $\text{mg/m}^3$) | $SO_2$ (24-hr, $\mu\text{g/m}^3$) | $NH_3$ (24-hr, $\mu\text{g/m}^3$) | $Pb$ (24-hr, $\mu\text{g/m}^3$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Good (0–50)** | 0–50 | 0–30 | 0–40 | 0–50 | 0–1.0 | 0–40 | 0–200 | 0–0.5 |
| **Satisfactory (51–100)** | 51–100 | 31–60 | 41–80 | 51–100 | 1.1–2.0 | 41–80 | 201–400 | 0.6–1.0 |
| **Moderate (101–200)** | 101–250 | 61–90 | 81–180 | 101–168 | 2.1–10.0 | 81–380 | 401–800 | 1.1–2.0 |
| **Poor (201–300)** | 251–350 | 91–120 | 181–280 | 169–208 | 10.1–17.0 | 381–800 | 801–1200 | 2.1–3.0 |
| **Very Poor (301–400)** | 351–430 | 121–250 | 281–400 | 209–748* | 17.1–34.0 | 801–1600 | 1201–1800 | 3.1–3.5 |
| **Severe (401–500)** | 430+ | 250+ | 400+ | 748+* | 34.0+ | 1600+ | 1800+ | 3.5+ |

*\*Note: Ozone concentrations above $208\,\mu\text{g/m}^3$ are evaluated using 1-hour monitoring values for sub-index computation.*

### Sub-Index Linear Interpolation Formula
For a pollutant concentration $C_p$ falling within breakpoint bounds $[BP_{LO}, BP_{HI}]$ corresponding to index bounds $[I_{LO}, I_{HI}]$, the individual sub-index $I_p$ is computed via linear interpolation:

$$I_p = I_{LO} + \left( \frac{I_{HI} - I_{LO}}{BP_{HI} - BP_{LO}} \right) \times (C_p - BP_{LO})$$

$$\text{Overall AQI} = \max(I_{PM10}, I_{PM2.5}, I_{NO2}, I_{O3}, I_{CO}, I_{SO2}, I_{NH3}, I_{Pb})$$

---

## 3. Health Impact Statements by AQI Category
Each CPCB AQI band corresponds to standardized public health advisories:

* **Good (0–50):** Minimal impact on health.
* **Satisfactory (51–100):** May cause minor breathing discomfort to sensitive individuals (e.g., those with asthma or allergies).
* **Moderate (101–200):** May cause breathing discomfort to people with lung diseases such as asthma, and discomfort to people with heart disease, children, and older adults.
* **Poor (201–300):** May cause breathing discomfort to most people on prolonged exposure, and discomfort to people with heart disease even on short exposure.
* **Very Poor (301–400):** May cause respiratory illness to people on prolonged exposure. Health effects are significantly more pronounced in individuals with pre-existing lung and heart conditions.
* **Severe (401–500):** May cause respiratory impacts even on healthy people, and serious health impacts on individuals with lung or heart disease. Symptoms may be experienced even during light physical activity.

---

## 4. Comparison: India CPCB NAAQS vs. WHO 2021 Global Air Quality Guidelines
Regulatory limits established under India's National Ambient Air Quality Standards (NAAQS) balance health protection with regional feasibility and natural background dust levels, whereas the World Health Organization (WHO) 2021 Global Air Quality Guidelines represent strict, health-based benchmarks:

| Pollutant | Averaging Period | India CPCB NAAQS Limit | WHO 2021 AQG Level |
| :--- | :--- | :--- | :--- |
| **$PM_{2.5}$** | 24-hour | $60\,\mu\text{g/m}^3$ | $15\,\mu\text{g/m}^3$ |
| **$PM_{2.5}$** | Annual | $40\,\mu\text{g/m}^3$ | $5\,\mu\text{g/m}^3$ |
| **$PM_{10}$** | 24-hour | $100\,\mu\text{g/m}^3$ | $45\,\mu\text{g/m}^3$ |
| **$PM_{10}$** | Annual | $60\,\mu\text{g/m}^3$ | $15\,\mu\text{g/m}^3$ |
| **$NO_2$** | 24-hour | $80\,\mu\text{g/m}^3$ | $25\,\mu\text{g/m}^3$ |
| **$NO_2$** | Annual | $40\,\mu\text{g/m}^3$ | $10\,\mu\text{g/m}^3$ |
| **$SO_2$** | 24-hour | $80\,\mu\text{g/m}^3$ | $40\,\mu\text{g/m}^3$ |
| **$O_3$** | 8-hour | $100\,\mu\text{g/m}^3$ | $100\,\mu\text{g/m}^3$ |
| **$CO$** | 8-hour (CPCB) / 24-hour (WHO) | $2\,\text{mg/m}^3$ | $4\,\text{mg/m}^3$ |

---

## 5. Why CPCB AQI Differs from WAQI / US-EPA Reported Numbers
Platforms such as the World Air Quality Index (WAQI) frequently display numerical values that differ from official CPCB dashboards for the exact same monitoring station due to three methodological differences:
1. **Breakpoint Scale Differences:** WAQI converts raw pollutant concentrations using the **US-EPA AQI** breakpoint table rather than CPCB breakpoints. Under US-EPA rules, a 24-hour $PM_{2.5}$ concentration of $60\,\mu\text{g/m}^3$ already exceeds an AQI of 150 ("Unhealthy"), whereas CPCB classifies $60\,\mu\text{g/m}^3$ at the top of "Satisfactory" (AQI 100).
2. **Averaging Period Differences:** CPCB mandates a strict 24-hour rolling average for particulate matter. Third-party aggregators often apply the US-EPA **NowCast** algorithm, which weights recent 1-to-3-hour readings more heavily when air quality is changing rapidly, causing faster spikes and drops than CPCB's 24-hour mean.
3. **Missing Pollutant Handling:** While CPCB refuses to publish an AQI if fewer than three pollutants (including at least one particulate metric) are valid over 16 hours, third-party platforms often compute a single-pollutant sub-index immediately from hourly $PM_{2.5}$ alone.

---

## 6. Meteorological Influences & Atmospheric Chemistry
* **Temperature & Thermal Inversions:** Under normal daytime conditions, warm surface air rises and disperses pollutants vertically. During winter nights and early mornings, surface cooling creates a **thermal inversion**—a layer of warm air trapping cold, dense air near the ground—preventing vertical mixing and causing severe spikes in $PM_{2.5}$, $PM_{10}$, and $CO$.
* **Wind Speed:** Low wind speeds ($< 2\,\text{m/s}$) lead to stagnation and local pollutant accumulation, whereas higher wind speeds disperse gaseous and fine particulate plumes (though extreme winds in dry regions can resuspend coarse crustal dust, elevating $PM_{10}$).
* **Relative Humidity:** High relative humidity ($> 70\%$) promotes **hygroscopic growth**, wherein water-soluble aerosols (sulfates, nitrates, ammonium) absorb moisture, swell in aerodynamic diameter, scatter more light (reducing visibility), and accelerate secondary particulate formation.
* **Solar Radiation & Ground-Level Ozone ($O_3$):** Unlike primary pollutants emitted directly from tailpipes, $O_3$ is formed photochemically when sunlight drives reactions between $NO_x$ and VOCs. Consequently, $O_3$ concentrations typically peak during hot, cloudless afternoons and drop after sunset when nitrogen oxide ($NO$) titrates remaining ozone.

---

## 7. Clinical & Physiological Effects of Major Pollutants
* **Fine Particulate Matter ($PM_{2.5}$):** Because particles are smaller than $2.5\,\mu\text{m}$, they bypass nasal and upper-airway filtration, penetrate deep into the pulmonary alveoli, and cross the alveolar-capillary membrane into systemic circulation. Acute exposure triggers airway inflammation, asthma exacerbations, and arrhythmias; chronic exposure increases risks of ischemic heart disease, stroke, chronic obstructive pulmonary disease (COPD), and lung cancer.
* **Coarse Particulate Matter ($PM_{10}$):** Particles between $2.5\,\mu\text{m}$ and $10\,\mu\text{m}$ deposit primarily in the upper respiratory tract, trachea, and bronchi, causing nasal irritation, coughing, phlegm production, and bronchitis.
* **Sulfur Dioxide ($SO_2$) & Nitrogen Dioxide ($NO_2$):** Both gases act as potent airway irritants. $SO_2$ dissolves rapidly in the moist lining of the upper airways, inducing immediate **bronchoconstriction** (airway narrowing), wheezing, and shortness of breath—particularly in individuals with asthma, who exhibit heightened bronchial reactivity even during brief exposures. $NO_2$ penetrates deeper into the lower respiratory tract, impairing mucociliary clearance and increasing susceptibility to viral and bacterial respiratory infections.
* **Carbon Monoxide ($CO$):** Binds to hemoglobin with an affinity over 200 times greater than oxygen, forming **carboxyhemoglobin** and reducing oxygen delivery to vital organs, which poses acute risks to individuals with coronary artery disease.