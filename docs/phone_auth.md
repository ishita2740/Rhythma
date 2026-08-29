Phone number + OTP (Firebase) authentication
===========================================

This backend expects the client to use Firebase Phone Auth (client SDK) to deliver
an OTP to the user's phone and obtain a verified Firebase ID token. The backend's
`POST /api/v1/auth/firebase-login` endpoint accepts that ID token, verifies it
with Firebase Admin, and then finds-or-creates the corresponding user account by
phone number.

Server responsibilities
- Verify the Firebase ID token using `firebase_admin.auth.verify_id_token`.
- Extract the `phone_number` from the decoded token.
- Find an existing user by phone, or create one if none exists.
- Issue an internal JWT and set an HttpOnly cookie for web clients.

Client responsibilities
- Use Firebase client SDK to send OTP and verify it on-device.
- Send the resulting ID token to `POST /api/v1/auth/firebase-login`.

Why this design?
- Firebase's client SDKs handle SMS delivery, reCAPTCHA/anti-abuse, and rate-limits on a per-phone basis.
- The backend only needs to trust Firebase's ID token; it does not send OTPs itself.

If you'd like the backend to send OTPs directly (not recommended unless you have a Twilio/Telco contract and anti-abuse controls), we can add explicit send/verify endpoints; open a follow-up issue and I can implement that.
