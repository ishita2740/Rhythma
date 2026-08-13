/**
 * Which translation key names each route.
 *
 * Reuses the `meta.*` keys #407 introduced for `document.title`, so a page
 * has one name rather than two that can drift apart — the tab and the
 * screen-reader announcement should never disagree about where the user
 * is.
 *
 * Lives here rather than in `RouteAnnouncer.tsx` so that file exports only
 * a component (fast refresh stops working for a module that mixes the
 * two), and so the mapping can be tested without rendering anything.
 */
const ROUTE_TITLE_KEYS: { pattern: RegExp; key: string }[] = [
  { pattern: /^\/$/, key: 'meta.home.title' },
  { pattern: /^\/cycle/, key: 'meta.cycle.title' },
  { pattern: /^\/assistant/, key: 'meta.assistant.title' },
  { pattern: /^\/insights/, key: 'meta.insights.title' },
  { pattern: /^\/profile/, key: 'meta.profile.title' },
  { pattern: /^\/settings/, key: 'meta.settings.title' },
  { pattern: /^\/sharing/, key: 'meta.sharing.title' },
  { pattern: /^\/sms/, key: 'meta.sms.title' },
  { pattern: /^\/login/, key: 'meta.login.title' },
  { pattern: /^\/register/, key: 'meta.register.title' },
  // Order matters: the specific provider routes come before the bare
  // `/provider` prefix, which would otherwise swallow all of them.
  { pattern: /^\/provider\/patients\//, key: 'meta.providerPatient.title' },
  { pattern: /^\/provider\/login/, key: 'meta.providerLogin.title' },
  { pattern: /^\/provider\/register/, key: 'meta.providerRegister.title' },
  { pattern: /^\/provider/, key: 'meta.providerDashboard.title' },
];

/**
 * The key naming this path, falling back to the app name.
 *
 * A fallback rather than an empty string: the announcer exists so that
 * *something* is said on navigation, and an unmapped route saying nothing
 * is the bug it was written to fix.
 */
export function routeTitleKey(pathname: string): string {
  const match = ROUTE_TITLE_KEYS.find((route) => route.pattern.test(pathname));
  return match ? match.key : 'meta.appName';
}
