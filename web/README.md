# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.

## Tests

```bash
npm test            # watch mode
npm run test:run    # single run, what CI executes
npm run test:coverage
```

Vitest + React Testing Library, running in jsdom. No test performs a real
network request — `src/api/client` is mocked at the module boundary and the
assertions are on the **URL and payload** each function sends, because that
is the class of bug (#259: a call to `/auth/token`, an endpoint the backend
does not serve) that type-checks, lints and builds cleanly and then fails
only at runtime.

`src/test/utils.tsx` provides `renderWithProviders`, which wraps a component
in the same Router / AuthProvider / i18n providers the real app mounts it
under, plus small fixtures for dashboard payloads and axios-shaped errors.
