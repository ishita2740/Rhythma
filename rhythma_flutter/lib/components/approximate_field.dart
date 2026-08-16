import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../config/theme.dart';

/// Describes one selectable range in an [ApproximateField].
///
/// The [key] is a stable identifier (e.g. `'under_18'`) used for storage and
/// analytics — it is NOT displayed.  The [label] should come from
/// localization so it adapts to the active locale.
class ApproxRange {
  /// Machine-readable key stored in profile maps and passed to analytics.
  final String key;

  /// Human-readable label sourced from i18n (e.g. "18–25").
  final String label;

  /// Numeric midpoint used when this range is selected but the user chose
  /// "Not sure".  Stored as the value in the profile map.
  final double midpoint;

  const ApproxRange({
    required this.key,
    required this.label,
    required this.midpoint,
  });
}

/// A composite field that lets users enter an exact numeric value *or* pick
/// an approximate range via a "Not sure" toggle.
///
/// When the user toggles "Not sure", the text field is disabled and a
/// vertical list of [RadioListTile] range options appears below.  The text
/// field's content is always preserved in [controller] so toggling back
/// restores the previous input.
class ApproximateField extends StatelessWidget {
  /// Label shown above the field (e.g. "Age" from i18n).
  final String label;

  /// Hint text for the text field (e.g. "Enter your age" from i18n).
  final String hint;

  /// Unit suffix shown in the text field (e.g. "years", "cm", "kg").
  final String unit;

  /// Available ranges for the "Not sure" picker.
  final List<ApproxRange> ranges;

  /// Controller for the exact-value text field.
  final TextEditingController controller;

  /// Whether the user is currently in "Not sure" / approximate mode.
  final bool isEstimated;

  /// Called when the "Not sure" switch is toggled.
  final ValueChanged<bool> onEstimatedChanged;

  /// Key of the currently selected range (matches [ApproxRange.key]).
  final String? selectedRange;

  /// Called when a range is selected.
  final ValueChanged<String> onRangeChanged;

  /// Validation error to display below the field.
  final String? error;

  /// Whether decimal input is allowed.
  final bool isDecimal;

  /// Minimum allowed value (for validation).
  final double minValue;

  /// Maximum allowed value (for validation).
  final double maxValue;

  /// Localized label for the "Not sure" toggle (e.g. "Not sure" from i18n).
  final String toggleLabel;

  /// Localized label shown in the "(Approximate)" chip when estimated
  /// (e.g. "Approximate" from i18n).
  final String approximateLabel;

  const ApproximateField({
    super.key,
    required this.label,
    required this.hint,
    required this.unit,
    required this.ranges,
    required this.controller,
    required this.isEstimated,
    required this.onEstimatedChanged,
    this.selectedRange,
    required this.onRangeChanged,
    this.error,
    this.isDecimal = false,
    this.minValue = 0,
    this.maxValue = 999,
    required this.toggleLabel,
    required this.approximateLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Label row with optional "(Approximate)" chip ───────────────
        Row(
          children: [
            Text(
              label,
              style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg),
            ),
            if (isEstimated) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: RhythmaColors.primary.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  '($approximateLabel)',
                  style: TextStyle(
                    fontSize: 11,
                    color: RhythmaColors.primary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: 8),

        // ── Exact text field ───────────────────────────────────────────
        TextField(
          controller: controller,
          keyboardType: isDecimal
              ? const TextInputType.numberWithOptions(decimal: true)
              : TextInputType.number,
          enabled: !isEstimated,
          inputFormatters: [
            FilteringTextInputFormatter.allow(
              isDecimal ? RegExp(r'[0-9.]') : RegExp(r'[0-9]'),
            ),
          ],
          style: TextStyle(color: RhythmaColors.foreground),
          decoration: InputDecoration(
            hintText: '$hint ($unit)',
            errorText: error,
            labelStyle: TextStyle(color: RhythmaColors.mutedFg),
            hintStyle: TextStyle(
              color: RhythmaColors.mutedFg.withValues(alpha: 0.6),
            ),
            filled: true,
            fillColor: isEstimated
                ? RhythmaColors.surface.withValues(alpha: 0.5)
                : RhythmaColors.surface,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide.none,
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary.withValues(alpha: 0.2),
              ),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary,
                width: 1.5,
              ),
            ),
            disabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(
                color: RhythmaColors.primary.withValues(alpha: 0.1),
              ),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: Colors.redAccent, width: 1.5),
            ),
          ),
        ),
        const SizedBox(height: 8),

        // ── "Not sure" toggle BELOW input area ─────────────────────────
        GestureDetector(
          onTap: () => onEstimatedChanged(!isEstimated),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Switch(
                value: isEstimated,
                onChanged: onEstimatedChanged,
                activeThumbColor: RhythmaColors.primary,
                inactiveThumbColor: RhythmaColors.mutedFg,
                activeTrackColor: RhythmaColors.primary.withValues(alpha: 0.3),
                inactiveTrackColor: RhythmaColors.surface,
              ),
              const SizedBox(width: 4),
              Text(
                toggleLabel,
                style: TextStyle(
                  fontSize: 13,
                  color: isEstimated
                      ? RhythmaColors.primary
                      : RhythmaColors.mutedFg,
                  fontWeight: isEstimated ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ],
          ),
        ),

        // ── Range picker (vertical RadioListTile) ──────────────────────
        if (isEstimated) ...[
          const SizedBox(height: 8),
          ...ranges.map((range) {
            final isSelected = selectedRange == range.key;
            return RadioListTile<String>(
              value: range.key,
              groupValue: selectedRange,
              onChanged: (v) {
                if (v != null) onRangeChanged(v);
              },
              title: Text(
                range.label,
                style: TextStyle(
                  fontSize: 14,
                  color: isSelected
                      ? RhythmaColors.primary
                      : RhythmaColors.foreground,
                ),
              ),
              activeColor: RhythmaColors.primary,
              contentPadding: EdgeInsets.zero,
              dense: true,
            );
          }),
        ],
      ],
    );
  }
}
