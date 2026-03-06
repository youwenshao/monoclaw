"""No-show risk predictor using gradient boosting (scikit-learn).

Falls back to rule-based heuristics when fewer than 200 bookings
are available for training.
"""

from __future__ import annotations

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from openclaw_shared.database import get_db

from fnb_hospitality.no_show_shield.scoring.reliability import (
    SCORE_NUMERIC,
    calculate_score,
)

logger = logging.getLogger("openclaw.fnb.no-show-shield.predictor")

MIN_TRAINING_SAMPLES = 200
MODEL_FILENAME = "no_show_model.pkl"

CHANNEL_ENCODING = {
    "whatsapp": 0,
    "phone": 1,
    "openrice": 2,
    "instagram": 3,
    "walk_in": 4,
    "website": 5,
}

RISK_THRESHOLDS = {"high": 0.65, "medium": 0.35}


def _encode_channel(channel: str) -> int:
    return CHANNEL_ENCODING.get(channel.lower(), len(CHANNEL_ENCODING))


def _extract_features(booking: dict[str, Any], reliability_score: str) -> list[float]:
    """Build feature vector from booking data.

    Features: reliability_score_numeric, party_size, day_of_week,
              lead_time_hours, channel_encoded
    """
    score_num = float(SCORE_NUMERIC.get(reliability_score, 3))
    party_size = float(booking.get("party_size", 2))

    booking_date = booking.get("booking_date", "")
    if booking_date:
        try:
            dow = datetime.fromisoformat(booking_date).weekday()
        except (ValueError, TypeError):
            dow = 3
    else:
        dow = 3

    created_at = booking.get("created_at", "")
    booking_dt_str = f"{booking.get('booking_date', '')} {booking.get('booking_time', '19:00')}"
    try:
        booking_dt = datetime.fromisoformat(booking_dt_str.strip())
        created = datetime.fromisoformat(created_at) if created_at else datetime.now()
        lead_hours = max(0, (booking_dt - created).total_seconds() / 3600)
    except (ValueError, TypeError):
        lead_hours = 48.0

    channel_enc = float(_encode_channel(booking.get("channel", "phone")))

    return [score_num, party_size, float(dow), lead_hours, channel_enc]


def _rule_based_predict(features: list[float]) -> dict[str, Any]:
    """Heuristic prediction when ML model is unavailable."""
    score_num, party_size, dow, lead_hours, channel_enc = features

    risk = 0.0

    if score_num <= 1:
        risk += 0.40
    elif score_num <= 2:
        risk += 0.25
    elif score_num <= 3:
        risk += 0.10

    if party_size >= 8:
        risk += 0.10
    elif party_size >= 6:
        risk += 0.05

    if dow in (4, 5):
        risk += 0.05

    if lead_hours > 168:
        risk += 0.10
    elif lead_hours > 72:
        risk += 0.05

    if channel_enc >= 4:
        risk += 0.05

    risk = min(risk, 0.95)

    factors = []
    if score_num <= 2:
        factors.append("low_reliability_score")
    if party_size >= 6:
        factors.append("large_party")
    if lead_hours > 72:
        factors.append("long_lead_time")
    if dow in (4, 5):
        factors.append("weekend_booking")
    if channel_enc >= 4:
        factors.append("low_commitment_channel")

    if risk >= RISK_THRESHOLDS["high"]:
        prediction = "high"
    elif risk >= RISK_THRESHOLDS["medium"]:
        prediction = "medium"
    else:
        prediction = "low"

    return {
        "risk_score": round(risk, 3),
        "risk_factors": factors,
        "prediction": prediction,
        "model_type": "rule_based",
    }


def _get_model_path(db_path: str) -> Path:
    return Path(db_path).parent / MODEL_FILENAME


def _has_enough_data(db_path: str) -> bool:
    with get_db(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM no_show_predictions WHERE actual_outcome IS NOT NULL"
        ).fetchone()[0]
    return count >= MIN_TRAINING_SAMPLES


def train_model(db_path: str) -> bool:
    """Train a GradientBoostingClassifier on historical data. Returns True on success."""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except ImportError:
        logger.warning("scikit-learn not available, cannot train model")
        return False

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.booking_id, p.risk_factors, p.actual_outcome,
                      g.reliability_score, g.phone
               FROM no_show_predictions p
               LEFT JOIN guests g ON g.phone = (
                   SELECT guest_phone FROM confirmations WHERE booking_id = p.booking_id LIMIT 1
               )
               WHERE p.actual_outcome IS NOT NULL"""
        ).fetchall()

    if len(rows) < MIN_TRAINING_SAMPLES:
        logger.info("Only %d samples, need %d to train", len(rows), MIN_TRAINING_SAMPLES)
        return False

    X = []
    y = []

    for row in rows:
        r = dict(row)
        factors = json.loads(r["risk_factors"]) if r.get("risk_factors") else []
        features_dict = {}
        for f in factors:
            if isinstance(f, dict):
                features_dict.update(f)

        score = r.get("reliability_score", "B")
        feature_vec = [
            float(SCORE_NUMERIC.get(score, 3)),
            features_dict.get("party_size", 2.0),
            features_dict.get("day_of_week", 3.0),
            features_dict.get("lead_time_hours", 48.0),
            features_dict.get("channel_encoded", 1.0),
        ]
        X.append(feature_vec)
        y.append(1 if r["actual_outcome"] == "no_show" else 0)

    X_arr = np.array(X)
    y_arr = np.array(y)

    clf = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
    )
    clf.fit(X_arr, y_arr)

    model_path = _get_model_path(db_path)
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)

    logger.info("Trained no-show model with %d samples, saved to %s", len(y), model_path)
    return True


def _load_model(db_path: str) -> Any | None:
    model_path = _get_model_path(db_path)
    if not model_path.exists():
        return None
    try:
        with open(model_path, "rb") as f:
            return pickle.load(f)  # noqa: S301
    except Exception:
        logger.exception("Failed to load model from %s", model_path)
        return None


def predict_no_show(db_path: str, booking_data: dict[str, Any]) -> dict[str, Any]:
    """Predict no-show risk for a booking.

    Returns dict with risk_score (0-1), risk_factors list,
    prediction ("low"/"medium"/"high"), model_type.
    """
    phone = booking_data.get("guest_phone", "")
    reliability = calculate_score(db_path, phone) if phone else "B"
    features = _extract_features(booking_data, reliability)

    model = None
    if _has_enough_data(db_path):
        model = _load_model(db_path)
        if model is None:
            train_model(db_path)
            model = _load_model(db_path)

    if model is not None:
        try:
            X = np.array([features])
            proba = model.predict_proba(X)[0]
            risk_score = float(proba[1]) if len(proba) > 1 else float(proba[0])

            feature_names = [
                "reliability_score", "party_size", "day_of_week",
                "lead_time_hours", "channel",
            ]
            importances = model.feature_importances_
            risk_factors = [
                feature_names[i]
                for i in np.argsort(importances)[::-1]
                if importances[i] > 0.1
            ]

            if risk_score >= RISK_THRESHOLDS["high"]:
                prediction = "high"
            elif risk_score >= RISK_THRESHOLDS["medium"]:
                prediction = "medium"
            else:
                prediction = "low"

            return {
                "risk_score": round(risk_score, 3),
                "risk_factors": risk_factors,
                "prediction": prediction,
                "model_type": "gradient_boosting",
            }
        except Exception:
            logger.exception("ML prediction failed, falling back to rules")

    return _rule_based_predict(features)


def record_prediction(
    db_path: str,
    booking_id: int,
    result: dict[str, Any],
) -> int:
    """Store a prediction in the database. Returns the prediction ID."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO no_show_predictions
               (booking_id, risk_score, risk_factors, prediction)
               VALUES (?, ?, ?, ?)""",
            (
                booking_id,
                result["risk_score"],
                json.dumps(result["risk_factors"]),
                result["prediction"],
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def record_outcome(db_path: str, booking_id: int, outcome: str) -> bool:
    """Record the actual outcome for a prediction."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "UPDATE no_show_predictions SET actual_outcome = ? WHERE booking_id = ?",
            (outcome, booking_id),
        )
    return cursor.rowcount > 0
