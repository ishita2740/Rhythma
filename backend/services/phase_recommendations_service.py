"""Cycle Phase Wellness Advisor service.

Given a user's current cycle phase (detected by prediction_service),
returns evidence-based wellness recommendations for sleep, nutrition,
exercise, and self-care — informed by the phase the user is actually in,
not a fixed calendar day.

Not medical advice.  These are general wellness suggestions derived from
the phase name and the user's own logged data.  The disclaimer is always
returned with every response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from services.firestore_service import UserService
from services.prediction_service import (
    PHASE_FOLLICULAR,
    PHASE_LATE,
    PHASE_LUTEAL,
    PHASE_OVULATION,
    PHASE_PERIOD,
    PHASE_UNKNOWN,
    predict,
)
from services.scoring_service import CycleService

DISCLAIMER = (
    "These are general wellness suggestions based on your cycle phase, "
    "not medical advice. Consult a healthcare professional for personalised guidance."
)
DISCLAIMER_KEY = "phase_recommendations.disclaimer"

# ─── Recommendation data ─────────────────────────────────────────────────────

_SLEEP: Dict[str, List[Dict[str, str]]] = {
    PHASE_PERIOD: [
        {"title": "Prioritise rest", "body": "Your body is working hard. Aim for 7–9 hours and consider a short nap if tired.", "tipKey": "sleep.period.rest"},
        {"title": "Warm bedtime routine", "body": "A warm bath or herbal tea before bed can ease cramps and improve sleep quality.", "tipKey": "sleep.period.warm_routine"},
    ],
    PHASE_FOLLICULAR: [
        {"title": "Leverage rising energy", "body": "Oestrogen is climbing. You may find it easier to fall asleep — maintain a consistent bedtime to lock in the habit.", "tipKey": "sleep.follicular.consistent"},
        {"title": "Morning light exposure", "body": "Get 10–15 minutes of natural light in the morning to anchor your circadian rhythm during this energetic phase.", "tipKey": "sleep.follicular.light"},
    ],
    PHASE_OVULATION: [
        {"title": "Watch for restlessness", "body": "Peak energy can make winding down harder. Dim screens 30 minutes before bed and avoid late caffeine.", "tipKey": "sleep.ovulation.wind_down"},
    ],
    PHASE_LUTEAL: [
        {"title": "Combat pre-period insomnia", "body": "Progesterone rises then drops, which can disrupt sleep. Keep the bedroom cool and stick to a wind-down routine.", "tipKey": "sleep.luteal.insomnia"},
        {"title": "Magnesium-rich foods", "body": "Foods like bananas, nuts, and dark chocolate may support better sleep during this phase.", "tipKey": "sleep.luteal.magnesium"},
    ],
    PHASE_LATE: [
        {"title": "Be gentle with yourself", "body": "Your cycle is running long. Reduce evening screen time and aim for a calming pre-sleep ritual.", "tipKey": "sleep.late.gentle"},
    ],
    PHASE_UNKNOWN: [
        {"title": "Build a sleep foundation", "body": "Consistent sleep and wake times support cycle regularity. Aim for 7–9 hours nightly.", "tipKey": "sleep.unknown.foundation"},
    ],
}

_NUTRITION: Dict[str, List[Dict[str, str]]] = {
    PHASE_PERIOD: [
        {"title": "Iron-rich foods", "body": "Leafy greens, lentils, and fortified cereals help replenish iron lost during menstruation.", "tipKey": "nutrition.period.iron"},
        {"title": "Anti-inflammatory foods", "body": "Ginger, turmeric, and fatty fish may help reduce menstrual inflammation and cramping.", "tipKey": "nutrition.period.anti_inflammatory"},
    ],
    PHASE_FOLLICULAR: [
        {"title": "Protein and sprouts", "body": "Rising oestrogen supports muscle repair. Include lean proteins and fresh sprouts in meals.", "tipKey": "nutrition.follicular.protein"},
        {"title": "Fermented foods", "body": "Yoghurt, idli, and curd support gut health, which is linked to oestrogen metabolism.", "tipKey": "nutrition.follicular.fermented"},
    ],
    PHASE_OVULATION: [
        {"title": "Fibre and antioxidants", "body": "Help your body clear excess oestrogen with fibre-rich vegetables and antioxidant-rich fruits.", "tipKey": "nutrition.ovulation.fibre"},
        {"title": "Stay hydrated", "body": "Water retention can fluctuate around ovulation. Aim for 2–3 litres daily.", "tipKey": "nutrition.ovulation.hydration"},
    ],
    PHASE_LUTEAL: [
        {"title": "Complex carbohydrates", "body": "Serotonin drops in the luteal phase. Whole grains and oats can stabilise mood and energy.", "tipKey": "nutrition.luteal.carbs"},
        {"title": "Reduce salt and sugar", "body": "Both worsen bloating and mood swings. Choose naturally sweet fruits instead.", "tipKey": "nutrition.luteal.reduce_salt"},
    ],
    PHASE_LATE: [
        {"title": "Balanced meals", "body": "Keep blood sugar steady with regular, balanced meals to manage any irritability.", "tipKey": "nutrition.late.balanced"},
    ],
    PHASE_UNKNOWN: [
        {"title": "Balanced plate", "body": "A mix of proteins, complex carbs, and healthy fats supports overall cycle health.", "tipKey": "nutrition.unknown.balanced"},
    ],
}

_EXERCISE: Dict[str, List[Dict[str, str]]] = {
    PHASE_PERIOD: [
        {"title": "Gentle movement", "body": "Light walking, yoga, or stretching can ease cramps without overexerting.", "tipKey": "exercise.period.gentle"},
        {"title": "Listen to your body", "body": "It is okay to rest entirely. Forcing intense workouts during heavy flow is counterproductive.", "tipKey": "exercise.period.listen"},
    ],
    PHASE_FOLLICULAR: [
        {"title": "High-intensity window", "body": "Rising oestrogen boosts endurance and strength. This is the best phase for HIIT, running, or strength training.", "tipKey": "exercise.follicular.high_intensity"},
        {"title": "Try something new", "body": "Energy and coordination peak — a great time to try a new class or sport.", "tipKey": "exercise.follicular.try_new"},
    ],
    PHASE_OVULATION: [
        {"title": "Peak performance", "body": "Your body is at its strongest. Push your limits safely with compound lifts or sprint work.", "tipKey": "exercise.ovulation.peak"},
        {"title": "Warm up thoroughly", "body": "Joint laxity peaks around ovulation. Spend extra time warming up to protect ligaments.", "tipKey": "exercise.ovulation.warmup"},
    ],
    PHASE_LUTEAL: [
        {"title": "Moderate, steady exercise", "body": "Yoga, swimming, or brisk walking maintain fitness without overtaxing a changing body.", "tipKey": "exercise.luteal.moderate"},
        {"title": "Reduce intensity gradually", "body": "As progesterone drops, your body tolerates less intensity. Scale back rather than pushing through.", "tipKey": "exercise.luteal.scale_back"},
    ],
    PHASE_LATE: [
        {"title": "Rest or very light movement", "body": "Your cycle is running long. Gentle stretching or walking is sufficient until your period arrives.", "tipKey": "exercise.late.rest"},
    ],
    PHASE_UNKNOWN: [
        {"title": "Stay active", "body": "Regular moderate exercise supports cycle regularity. Aim for 150 minutes per week.", "tipKey": "exercise.unknown.active"},
    ],
}

_SELFCARE: Dict[str, List[Dict[str, str]]] = {
    PHASE_PERIOD: [
        {"title": "Heat therapy", "body": "A warm compress or hot water bottle on the lower abdomen can relieve cramps naturally.", "tipKey": "selfcare.period.heat"},
        {"title": "Reduce obligations", "body": "Give yourself permission to say no. Period days are not the time for extra commitments.", "tipKey": "selfcare.period.reduce"},
    ],
    PHASE_FOLLICULAR: [
        {"title": "Plan social activities", "body": "Rising oestrogen boosts mood and sociability. Schedule catch-ups, creative projects, or brainstorming sessions.", "tipKey": "selfcare.follicular.social"},
        {"title": "Set new goals", "body": "Energy and optimism are high. Use this window to set intentions for the cycle ahead.", "tipKey": "selfcare.follicular.goals"},
    ],
    PHASE_OVULATION: [
        {"title": "Communicate openly", "body": "Confidence peaks. Important conversations, presentations, or interviews are well-timed now.", "tipKey": "selfcare.ovulation.communicate"},
    ],
    PHASE_LUTEAL: [
        {"title": "Journaling", "body": "Mood can fluctuate. Journaling helps process emotions and identify patterns over time.", "tipKey": "selfcare.luteal.journal"},
        {"title": "Boundary setting", "body": "Irritability is common. Protect your energy by setting clear boundaries this week.", "tipKey": "selfcare.luteal.boundaries"},
    ],
    PHASE_LATE: [
        {"title": "Self-compassion", "body": "A long cycle can be frustrating. Practice patience and avoid comparing to past cycles.", "tipKey": "selfcare.late.compassion"},
    ],
    PHASE_UNKNOWN: [
        {"title": "Track daily", "body": "Logging symptoms and mood daily helps build a picture of your unique patterns over time.", "tipKey": "selfcare.unknown.track"},
    ],
}

ALL_RECOMMENDATIONS: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "sleep": _SLEEP,
    "nutrition": _NUTRITION,
    "exercise": _EXERCISE,
    "self_care": _SELFCARE,
}


def _get_user_phase(user_id: str) -> str:
    """Detect the user's current phase from their logged data."""
    logs = CycleService.get_logs_for_user(user_id, limit=10)
    profile = UserService.get_user_by_id(user_id) or {}
    prediction = predict(logs, profile=profile, today=date.today())
    return prediction.phase


def _build_category(category_data: Dict[str, List[Dict[str, str]]], phase: str) -> List[Dict[str, str]]:
    """Return recommendations for a phase, falling back to unknown."""
    return category_data.get(phase, category_data.get(PHASE_UNKNOWN, []))


# ─── Public API ──────────────────────────────────────────────────────────────


def get_all_recommendations(user_id: str) -> Dict[str, Any]:
    """Phase-aware wellness recommendations across all categories."""
    phase = _get_user_phase(user_id)
    return {
        "phase": phase,
        "categories": {
            cat: _build_category(cat_data, phase)
            for cat, cat_data in ALL_RECOMMENDATIONS.items()
        },
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }


def get_category_recommendations(user_id: str, category: str) -> Dict[str, Any]:
    """Recommendations for one category (sleep, nutrition, exercise, self_care)."""
    if category not in ALL_RECOMMENDATIONS:
        raise ValueError(f"Unknown category '{category}'. Choose from: {list(ALL_RECOMMENDATIONS.keys())}")
    phase = _get_user_phase(user_id)
    return {
        "phase": phase,
        "category": category,
        "recommendations": _build_category(ALL_RECOMMENDATIONS[category], phase),
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }


def get_all_phases_summary() -> Dict[str, Any]:
    """Static overview of recommendations for every phase — no user data needed.

    Useful for the onboarding flow or an educational page showing what
    each phase typically involves.
    """
    phases = [PHASE_PERIOD, PHASE_FOLLICULAR, PHASE_OVULATION, PHASE_LUTEAL, PHASE_LATE, PHASE_UNKNOWN]
    summary = {}
    for phase in phases:
        summary[phase] = {
            cat: _build_category(cat_data, phase)
            for cat, cat_data in ALL_RECOMMENDATIONS.items()
        }
    return {
        "phases": summary,
        "phaseOrder": phases,
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }
