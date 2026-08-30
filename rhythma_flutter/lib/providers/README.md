# Providers Directory

This directory contains the State Management classes for Rhythma. We use the `provider` package to manage app-wide state and dependency injection.

## Current Providers

- **`cycle_provider.dart`**: Manages the user's menstrual cycle data, including fetching logs, calculating averages, and providing data to the UI.
- **`data_mode_provider.dart`**: Manages the user's privacy mode (online vs offline).
- **`locale_provider.dart`**: Manages the active localization/language state of the application.
- **`profile_provider.dart`**: Manages the user's profile information (name, avatar, settings).
- **`sync_status_provider.dart`**: Tracks the synchronization state between local Hive storage and remote Firebase/API.
- **`theme_provider.dart`**: Manages the application's visual theme (light/dark mode).

## Deprecated Providers

- **`dashboard_provider.dart`**: Removed in #431. Dashboard state is now managed locally in the Home screen to prevent unnecessary global state pollution.
