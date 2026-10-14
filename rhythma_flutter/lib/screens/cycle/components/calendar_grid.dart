import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../config/theme.dart';
import '../../../providers/cycle_provider.dart';
import '../../../services/local_storage_service.dart';
import 'log_entry_sheet.dart';

class CalendarGrid extends StatefulWidget {
  final PageController pageController;
  final int initialPageOffset;

  const CalendarGrid({
    super.key,
    required this.pageController,
    required this.initialPageOffset,
  });

  @override
  State<CalendarGrid> createState() => _CalendarGridState();
}

class _CalendarGridState extends State<CalendarGrid> {
  /// The month at [index], counted from the month the user is in *now*.
  ///
  /// Takes "now" from the provider rather than calling `DateTime.now()`
  /// here. Two components independently asking the clock is what let the
  /// grid and the provider disagree about which day it was (issue #539):
  /// the grid drew today's cell as tappable while the provider — holding a
  /// day captured at app launch — rejected the tap as a future date, so
  /// nothing happened at all.
  DateTime _monthForIndex(int index, DateTime today) {
    return DateTime(today.year, today.month + (index - widget.initialPageOffset));
  }

  @override
  Widget build(BuildContext context) {
    final cycleProvider = context.watch<CycleProvider>();
    // One answer to "what day is it" for this whole build, resolved fresh
    // rather than captured at construction.
    final today = cycleProvider.today;

    // Calculate cell width based on screen size, similar to before
    final cellWidth = (MediaQuery.of(context).size.width - 40 - 32) / 7;

    return SizedBox(
      height: 330, // Approximate fixed height to prevent PageView issues
      child: PageView.builder(
        controller: widget.pageController,
        onPageChanged: (index) {
          final month = _monthForIndex(index, today);
          // Only update if it's different to avoid loops
          if (cycleProvider.displayedMonth.year != month.year ||
              cycleProvider.displayedMonth.month != month.month) {
            // We use read to avoid calling setState during build/scroll
            context.read<CycleProvider>().setDisplayedMonth(month);
          }
        },
        itemBuilder: (context, index) {
          final monthDate = _monthForIndex(index, today);
          final monthDays =
              DateTime(monthDate.year, monthDate.month + 1, 0).day;
          final firstWeekday =
              DateTime(monthDate.year, monthDate.month, 1).weekday % 7;

          return Wrap(
            children: [
              // Empty cells for the leading gap
              ...List.generate(
                firstWeekday,
                (_) => SizedBox(width: cellWidth, height: 46),
              ),
              // Actual days
              ...List.generate(monthDays, (i) {
                final day = i + 1;
                final currentDate =
                    DateTime(monthDate.year, monthDate.month, day);
                final phaseColor = cycleProvider.phaseColor(currentDate);

                final isSelected =
                    cycleProvider.selectedDate.year == currentDate.year &&
                        cycleProvider.selectedDate.month == currentDate.month &&
                        cycleProvider.selectedDate.day == currentDate.day;

                final isToday = today.year == currentDate.year &&
                    today.month == currentDate.month &&
                    today.day == currentDate.day;

                final hasLog = cycleProvider.hasLogsForDate(currentDate);

                // `today` is already midnight-normalised by the provider, so
                // this compares whole days rather than an instant.
                final isFuture = currentDate.isAfter(today);

                return GestureDetector(
                  // Keyed by the date it represents so a test can address
                  // one specific cell. `find.text('11')` is ambiguous — the
                  // PageView may have built a neighbouring month that also
                  // has an 11th — and the whole point of #539 was two
                  // components disagreeing about which day a cell is.
                  key: ValueKey(currentDate),
                  onTap: isFuture
                      ? null
                      : () {
                          context.read<CycleProvider>().selectDate(currentDate);
                        },
                  child: SizedBox(
                    width: cellWidth,
                    height: 46,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          width: 34,
                          height: 34,
                          decoration: BoxDecoration(
                            color: isFuture
                                ? Colors.transparent
                                : isSelected
                                    ? phaseColor
                                    : phaseColor.withOpacity(0.14),
                            borderRadius: BorderRadius.circular(10),
                            border: isToday && !isSelected
                                ? Border.all(color: phaseColor, width: 1.4)
                                : null,
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                '$day',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: isToday && !isSelected
                                      ? FontWeight.w800
                                      : FontWeight.w600,
                                  color: isFuture
                                      ? RhythmaColors.mutedFg.withOpacity(0.4)
                                      : isSelected
                                          ? Colors.white
                                          : RhythmaColors.foreground,
                                ),
                              ),
                              // Marker for logged symptoms
                              if (hasLog)
                                Container(
                                  margin: const EdgeInsets.only(top: 1),
                                  width: 4,
                                  height: 4,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color:
                                        isSelected ? Colors.white : phaseColor,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ],
          );
        },
      ),
    );
  }
}