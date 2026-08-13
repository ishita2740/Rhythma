\# Health Disclaimers — Canonical Wording



This document tracks the canonical disclaimer copy used across Rhythma's

platforms (backend SMS, web app, Flutter app), so future changes stay

consistent and don't drift between surfaces.



\## Backend — SMS cycle summaries

> Estimate only, not medical/contraceptive advice.



Appended to SMS summaries only when the combined message fits within the

160-character SMS limit. If it doesn't fit, the disclaimer is omitted

entirely rather than sent truncated. See `backend/api/sms.py`.



\## Web \& Flutter — Home page fertile window

> This is an estimate based on your logged data, not medical or

> contraceptive advice.



Shown directly under the fertile window callout on the home screen.



\## Web \& Flutter — AI Assistant

> This assistant provides general wellness information only and is not a

> substitute for professional medical advice.



Shown persistently under the assistant page/screen header.



\## Web \& Flutter — Insights

> These insights are based on the information you log and are intended

> for personal tracking only. They are not a medical diagnosis and should

> not replace advice from a qualified healthcare professional.



Shown at the bottom of the insights page/screen.



\## Flutter — PDF health report export

> This report is an estimate based on self-logged data and is not a

> medical diagnosis. Please consult a qualified healthcare professional

> for medical advice.



Appended to the end of every generated PDF health report.



\## Translation status



Disclaimer copy has been added to all locales with an existing `home`/ARB

key structure. \*\*Non-English translations (hi, mr, ta, te, kn, ml, gu, bn)

were drafted by an AI assistant and have not been reviewed by a native

speaker.\*\* Given this is health-safety copy, a native-speaker review is

strongly recommended before these ship to production users.



Web locale files `gu.json` and `bn.json` are pre-existing partial/incomplete

locales (per the repo's own locale test suite) and were intentionally left

without the new key rather than silently marking them as complete.

