from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from src.api.waqi_client import POLLUTANT_KEYS
from src.core.aqi_engine import classify_aqi_category, evaluate_aqi

FEATURE_BASE_COLS: tuple[str, ...] = POLLUTANT_KEYS
LAG_FEATURE_COLS: tuple[str, ...] = tuple(f"{k}_lag1" for k in POLLUTANT_KEYS) + (
    "prev_aqi_lag1",
)


@dataclass
class PreprocessedDataset:
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: list[str]
    imputer: SimpleImputer
    scaler: StandardScaler
    total_cleaned_rows: int
    total_supervised_pairs: int
    used_lag_features: bool
    warnings: list[str] = field(default_factory=list)


def _derive_row_aqi_and_category(row: dict[str, Any]) -> tuple[float | None, str]:
    pol_map = {k: row.get(k) for k in POLLUTANT_KEYS}
    eng = evaluate_aqi(pol_map, waqi_reported_aqi=row.get("waqi_reported_aqi"))
    if eng.calculated_aqi is not None:
        return float(eng.calculated_aqi), eng.category

    calc = row.get("calculated_aqi")
    if calc is not None and not isinstance(calc, bool):
        try:
            val = float(calc)
            if val == val and val >= 0:
                cat = str(row.get("aqi_category") or classify_aqi_category(val))
                return val, cat if cat != "Unavailable" else classify_aqi_category(val)
        except (TypeError, ValueError):
            pass

    waqi = row.get("waqi_reported_aqi")
    if waqi is not None and not isinstance(waqi, bool):
        try:
            val = float(waqi)
            if val == val and val >= 0:
                return val, classify_aqi_category(val)
        except (TypeError, ValueError):
            pass

    return None, "Unavailable"


def clean_historical_observations(observations: list[dict[str, Any]]) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate and clean multi-observation historical records without fabricating synthetic rows.
    Rejects negative measurements, non-finite numbers, and rows lacking both timestamp and valid AQI.
    """
    warnings: list[str] = []
    if not observations:
        return pd.DataFrame(), ["No historical observations provided."]

    cleaned_rows: list[dict[str, Any]] = []
    dropped_invalid = 0

    for raw in observations:
        rec: dict[str, Any] = {
            "station_name": str(raw.get("station_name") or raw.get("query_city") or "Unknown"),
            "observation_time": str(raw.get("observation_time") or ""),
        }

        is_valid_flag = raw.get("is_valid")
        if is_valid_flag is not None and int(is_valid_flag) == 0:
            dropped_invalid += 1
            continue

        has_any_valid_pollutant = False
        has_bad_pollutant = False

        for key in POLLUTANT_KEYS:
            val = raw.get(key)
            if val is None or isinstance(val, bool):
                rec[key] = np.nan
                continue
            try:
                fval = float(val)
            except (TypeError, ValueError):
                rec[key] = np.nan
                has_bad_pollutant = True
                continue
            if np.isnan(fval) or np.isinf(fval) or fval < 0.0:
                rec[key] = np.nan
                has_bad_pollutant = True
            else:
                rec[key] = fval
                has_any_valid_pollutant = True

        aqi_val, category = _derive_row_aqi_and_category(rec)
        if aqi_val is None or category == "Unavailable" or not has_any_valid_pollutant:
            dropped_invalid += 1
            continue

        if has_bad_pollutant:
            warnings.append("Some negative or non-numeric pollutant entries were excluded during cleaning.")

        rec["row_aqi"] = aqi_val
        rec["current_category"] = category
        cleaned_rows.append(rec)

    if dropped_invalid > 0:
        warnings.append(f"Excluded {dropped_invalid} invalid or incomplete historical record(s).")

    if not cleaned_rows:
        return pd.DataFrame(), warnings

    df = pd.DataFrame(cleaned_rows)
    df["parsed_time"] = pd.to_datetime(df["observation_time"], errors="coerce", utc=True)
    df = df.sort_values(by=["parsed_time", "observation_time"], ascending=True).reset_index(drop=True)
    return df, warnings


def build_supervised_severity_dataset(
    observations: list[dict[str, Any]],
    test_size: float = 0.25,
) -> PreprocessedDataset:
    """
    Build chronological next-observation (t+1) severity classification samples from historical observations.
    Requires at least 4 cleaned observations so train and test sets each have real samples.
    """
    cleaned_df, warnings = clean_historical_observations(observations)
    if len(cleaned_df) < 4:
        raise ValueError(
            f"At least 4 valid historical observations are required for chronological train/test split; "
            f"found {len(cleaned_df)}."
        )

    work = cleaned_df.copy()
    use_lags = len(work) >= 8
    if use_lags:
        for key in POLLUTANT_KEYS:
            work[f"{key}_lag1"] = work[key].shift(1)
        work["prev_aqi_lag1"] = work["row_aqi"].shift(1)
        feature_cols = list(FEATURE_BASE_COLS) + list(LAG_FEATURE_COLS)
    else:
        warnings.append(
            "Fewer than 8 observations available; using current-step pollutant features without lag columns."
        )
        feature_cols = list(FEATURE_BASE_COLS)

    # Next-observation severity target (t+1)
    work["next_category"] = work["current_category"].shift(-1)

    # Drop last row (no next observation) and any row lacking lag features when lags are enabled
    supervised_df = work.dropna(subset=["next_category"]).copy()
    if use_lags:
        supervised_df = supervised_df.dropna(subset=list(LAG_FEATURE_COLS)).copy()

    if len(supervised_df) < 4:
        raise ValueError(
            f"Insufficient supervised next-step pairs ({len(supervised_df)}) after alignment."
        )

    X_raw = supervised_df[feature_cols].to_numpy(dtype=float)
    y_all = supervised_df["next_category"].astype(str).to_numpy()

    split_idx = max(1, min(len(supervised_df) - 1, int(round(len(supervised_df) * (1.0 - test_size)))))
    X_train_raw, X_test_raw = X_raw[:split_idx], X_raw[split_idx:]
    y_train, y_test = y_all[:split_idx], y_all[split_idx:]

    imputer = SimpleImputer(strategy="median")
    X_train_imp = imputer.fit_transform(X_train_raw)
    X_test_imp = imputer.transform(X_test_raw)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_imp)
    X_test_scaled = scaler.transform(X_test_imp)

    return PreprocessedDataset(
        X_train=X_train_scaled,
        X_test=X_test_scaled,
        y_train=y_train,
        y_test=y_test,
        feature_names=feature_cols,
        imputer=imputer,
        scaler=scaler,
        total_cleaned_rows=int(len(cleaned_df)),
        total_supervised_pairs=int(len(supervised_df)),
        used_lag_features=use_lags,
        warnings=warnings,
    )