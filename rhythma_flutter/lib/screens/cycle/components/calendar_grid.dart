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
  DateTime _monthForIndex(int index) {
    final now = DateTime.now();
    return DateTime(now.year, now.month + (index - widget.initialPageOffset));
  }

  @override
  Widget build(BuildContext context) {
    final cycleProvider = context.watch<CycleProvider>();

    // Calculate cell width based on screen size, similar to before
    final cellWidth = (MediaQuery.of(context).size.width - 40 - 32) / 7;

    return SizedBox(
      height: 330, // Approximate fixed height to prevent PageView issues
      child: PageView.builder(
        controller: widget.pageController,
        onPageChanged: (index) {
          final month = _monthForIndex(index);
          // Only update if it's different to avoid loops
          if (cycleProvider.displayedMonth.year != month.year ||
              cycleProvider.displayedMonth.month != month.month) {
            // We use read to avoid calling setState during build/scroll
            context.read<CycleProvider>().setDisplayedMonth(month);
          }
        },
        itemBuilder: (context, index) {
          final monthDate = _monthForIndex(index);
          final monthDays =
              DateTime(monthDate.year, monthDate.month + 1, 0).day;
          final firstWeekday =
              DateTime(monthDate.year, monthDate.month, 1).weekday % 7;

          final today = DateTime.now();

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

                final isFuture = currentDate.isAfter(DateTime(today.year, today.month, today.day));

                return GestureDetector(
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