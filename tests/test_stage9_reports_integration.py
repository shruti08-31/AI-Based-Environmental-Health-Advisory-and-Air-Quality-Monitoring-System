from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src.analytics.environmental_reports import (
    generate_environmental_report,
    report_to_csv_bytes,
    report_to_pdf_bytes,
)
from src.api.waqi_client import AqiReading
from src.database.repository import save_observation_bundle


def test_reports_insufficient_data_and_pdf_csv_export(tmp_path: Path) -> None:
    db_file = tmp_path / "reports_test.db"
    ref_day = date(2026, 11, 24)

    # Empty DB -> Daily/Weekly/Monthly all report insufficient data
    empty_daily = generate_environmental_report("Daily", reference_date=ref_day, db_path=db_file)
    assert empty_daily.sufficient_data is False

    base_dt = datetime(2026, 11, 24, 10, 0, 0, tzinfo=timezone.utc)
    for idx in range(4):
        r = AqiReading(
            query="Delhi",
            station_name="ITO, Delhi",
            aqi=120 + idx * 25,
            aqi_raw=120 + idx * 25,
            dominant_pollutant="pm25",
            pollutants={
                "pm25": 70.0 + idx * 15.0,
                "pm10": 110.0 + idx * 20.0,
                "no2": 35.0,
                "so2": 12.0,
                "co": 1.1,
                "o3": 30.0,
            },
            latitude=28.6289,
            longitude=77.2405,
            observation_time=(base_dt - timedelta(days=idx * 2)).isoformat(),
        )
        save_observation_bundle(r, db_path=db_file)

    daily = generate_environmental_report("Daily", reference_date=ref_day, db_path=db_file)
    assert daily.sufficient_data is True
    assert daily.average_aqi is not None
    assert daily.highest_aqi is not None and daily.lowest_aqi is not None

    weekly = generate_environmental_report("Weekly", reference_date=ref_day, db_path=db_file)
    assert weekly.sufficient_data is True
    assert weekly.observation_count >= 2

    monthly = generate_environmental_report("Monthly", reference_date=ref_day, db_path=db_file)
    assert monthly.sufficient_data is True
    assert monthly.observation_count >= 3

    pdf_bytes = report_to_pdf_bytes(weekly)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500

    csv_bytes = report_to_csv_bytes(weekly)
    assert b"calculated_aqi" in csv_bytes
    assert b"ITO, Delhi" in csv_bytes