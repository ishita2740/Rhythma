# Proposed Direction for Menstrual Insights

First of all, thank you for the effort put into building the ML training pipeline, fallback support, documentation, and tests. The engineering work is well structured and appreciated.

However, after reviewing the implementation carefully, I've decided **not to ship clinically sounding ML scores (CVI/MHS) in the public version of the app.** Since Rhythma is intended for real users, especially women relying on it for menstrual health tracking, I want to ensure that every insight we present is accurate, transparent, and not misleading.

## Why we're changing direction

The current implementation trains models entirely on synthetic data generated from hand-crafted formulas. While this is useful for demonstrating an ML pipeline and validating engineering, it does **not** make the resulting scores clinically meaningful or medically validated.

Because of this, I don't feel comfortable presenting outputs such as:

- "High Risk"
- "Potential PCOS"
- "Hormonal Variability"
- "Menstrual Health Score"
- "Cycle Variability Index"

These names and labels can easily be interpreted as medical assessments, even though they are not based on clinical validation.

Our goal should be to help users understand **their own data**, not diagnose medical conditions.

---

# New Direction

Instead of producing health or risk scores, the app should focus on presenting clear, factual summaries of the user's logged information.

## Keep

### Period Tracking

- Last period
- Current cycle
- Calendar
- Predicted next period (clearly labelled as an estimate)

---

### Cycle Statistics

Show factual values such as:

- Average cycle length
- Shortest cycle
- Longest cycle
- Average bleeding duration

These are directly calculated from the user's logs.

---

### Cycle Consistency

Rather than producing a numerical "risk" score, simply describe consistency.

Examples:

- Your cycle length has varied by 6 days over the last 6 cycles.
- Your recent cycles have been fairly consistent.
- Your cycles have become slightly more variable over the last three months.

These statements describe observable patterns without implying diagnosis.

---

### Trends

Provide trend analysis based on logged information, for example:

- Average sleep has decreased this month.
- Reported stress has increased compared with last month.
- You logged fewer cramps this cycle.
- Headaches have become less frequent.
- Symptom frequency has remained stable.

These insights are based entirely on user-entered data.

---

### Visualizations

Continue showing graphs for:

- Cycle lengths over time
- Bleeding duration
- Sleep trends
- Stress trends
- Symptom frequency

Graphs help users understand their own patterns without assigning medical meaning.

---

### Educational Content

Include educational articles from trusted medical organizations such as:

- World Health Organization (WHO)
- American College of Obstetricians and Gynecologists (ACOG)
- NHS
- Government health agencies

Whenever possible, provide the original source so users can verify the information themselves.

---

## Disclaimer

Every insights page should clearly state:

> These insights are based on the information you log and are intended for personal tracking only. They are **not** a medical diagnosis and should not replace advice from a qualified healthcare professional.

---

## Concerning Symptoms

If users repeatedly log symptoms such as:

- Severe pain
- Very heavy bleeding
- Fainting
- Bleeding lasting unusually long
- Frequent bleeding between periods

the app should avoid assigning scores and instead recommend seeking medical advice.

Example:

> Some symptoms may require medical attention. If you're experiencing severe pain, unusually heavy bleeding, fainting, or prolonged bleeding, please consult a qualified healthcare professional.

---

# Language Guidelines

The application should describe observations rather than making judgments.

Instead of:

> Your CVI is 72 — High Risk.

Use wording like:

> Your cycle length has ranged from 26 to 37 days over the last six months. If this feels different from what is normal for you or you have concerns, consider discussing it with a healthcare professional.

This communicates the same information while remaining factual and responsible.

---

# Remove

The following concepts should not appear in the public application unless they are clinically validated in the future:

- Cycle Variability Index (CVI)
- Menstrual Health Score (MHS)
- Risk scores
- AI-detected health conditions
- PCOS indicators
- Hormonal variability scores
- Numerical health scores out of 100
- Labels such as "High Risk", "Medium Risk", or "Low Risk"

Similarly, avoid star ratings or numerical judgments for sleep, stress, or symptoms unless they are based on established medical standards.

---

# Optional Summary Cards

If we still want concise dashboard summaries, they should be descriptive rather than evaluative.

### Cycle Consistency

- Consistent
- Slightly More Variable
- Variable

### Wellness Snapshot

Display a summary of:

- Average sleep
- Average stress
- Logged symptoms
- Cycle consistency

These summaries should simply organize the user's own information rather than calculate a medical score.

---

# Future Work

The ML pipeline, training scripts, and model-loading infrastructure can remain in an experimental or research branch until they are trained and validated using appropriate real-world datasets and reviewed with clinical guidance.

---

# Guiding Principle

Every insight shown in the app should answer one question:

**"Is this statement directly supported by the user's logged data?"**

If yes, we can display it.

If it requires assuming a diagnosis, estimating disease risk, or making a medical judgment, we should not present it.

The goal is to build an application that is trustworthy, transparent, and genuinely helpful for menstrual health tracking while leaving room for clinically validated features in the future.
