import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../config/theme.dart';

/// Circular progress ring — mirrors the SVG CycleRing in index.tsx
class CycleRing extends StatelessWidget {
  final int day;
  final int total;
  final double size;

  const CycleRing({
    super.key,
    required this.day,
    required this.total,
    this.size = 84,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(day: day, total: total),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                'Day',
                style: TextStyle(
                  fontSize: size * 0.13,
                  fontWeight: FontWeight.w500,
                  color: RhythmaColors.mutedFg,
                  letterSpacing: 0.5,
                ),
              ),
              Text(
                '$day',
                style: TextStyle(
                  fontSize: size * 0.30,
                  fontWeight: FontWeight.w700,
                  color: RhythmaColors.foreground,
                  height: 1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final int day;
  final int total;

  _RingPainter({required this.day, required this.total});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 6;
    const strokeWidth = 6.5;
    const startAngle = -math.pi / 2;

    // Track (lavender bg)
    final trackPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..color = RhythmaColors.lavender.withOpacity(0.5)
      ..strokeCap = StrokeCap.round;

    canvas.drawCircle(center, radius, trackPaint);

    // Progress arc with gradient
    final sweepAngle = (day / total) * 2 * math.pi;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final progressPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [RhythmaColors.primary, RhythmaColors.rose],
        startAngle: 0,
        endAngle: math.pi * 2,
        transform: const GradientRotation(-math.pi / 2),
      ).createShader(rect);

    canvas.drawArc(
      rect,
      startAngle,
      sweepAngle,
      false,
      progressPaint,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.day != day || old.total != total;
}

/// Score ring for Insights screen — larger, shows percentage value
class ScoreRing extends StatelessWidget {
  final int value;
  final double size;

  const ScoreRing({super.key, required this.value, this.size = 96});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _ScorePainter(value: value),
        child: Center(
          child: Text(
            '$value',
            style: TextStyle(
              fontSize: size * 0.28,
              fontWeight: FontWeight.w700,
              color: RhythmaColors.foreground,
            ),
          ),
        ),
      ),
    );
  }
}

class _ScorePainter extends CustomPainter {
  final int value;
  _ScorePainter({required this.value});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 7;
    const sw = 7.0;

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = sw
      ..color = RhythmaColors.lavender.withOpacity(0.5);
    canvas.drawCircle(center, radius, track);

    final rect = Rect.fromCircle(center: center, radius: radius);
    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = sw
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        colors: [RhythmaColors.primary, RhythmaColors.rose],
        startAngle: 0,
        endAngle: math.pi * 2,
        transform: const GradientRotation(-math.pi / 2),
      ).createShader(rect);

    canvas.drawArc(rect, -math.pi / 2, (value / 100) * 2 * math.pi, false, arc);
  }

  @override
  bool shouldRepaint(_ScorePainter old) => old.value != value;
}

/// Sparkline chart for cycle trend
class TrendChart extends StatelessWidget {
  final List<double> points;
  final Color? color;
  final double height;

  const TrendChart({
    super.key,
    required this.points,
    this.color,
    this.height = 80,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: height,
      child: CustomPaint(
        painter: _SparkPainter(
            points: points, color: color ?? RhythmaColors.primary),
        size: Size.infinite,
      ),
    );
  }
}

class _SparkPainter extends CustomPainter {
  final List<double> points;
  final Color color;

  _SparkPainter({required this.points, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (points.isEmpty) return;
    final minV = points.reduce(math.min);
    final maxV = points.reduce(math.max);
    final range = (maxV - minV).clamp(1.0, double.infinity);
    final step = size.width / (points.length - 1);

    double x(int i) => i * step;
    double y(double v) =>
        size.height -
        ((v - minV) / range) * size.height * 0.85 -
        size.height * 0.075;

    final path = Path();
    for (int i = 0; i < points.length; i++) {
      i == 0
          ? path.moveTo(x(i), y(points[i]))
          : path.lineTo(x(i), y(points[i]));
    }

    final areaPath = Path.from(path)
      ..lineTo(x(points.length - 1), size.height)
      ..lineTo(0, size.height)
      ..close();

    canvas.drawPath(
      areaPath,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withOpacity(0.35), color.withOpacity(0.0)],
        ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)),
    );

    canvas.drawPath(
      path,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round
        ..color = color,
    );

    for (int i = 0; i < points.length; i++) {
      canvas.drawCircle(
        Offset(x(i), y(points[i])),
        2.5,
        Paint()..color = color,
      );
    }
  }

  @override
  bool shouldRepaint(_SparkPainter old) => old.points != points;
}
