import 'package:flutter/material.dart';
import '../../config/theme.dart';

/// Educational screen designed specifically for first-time or teen users,
/// providing approachable, beginner-friendly guidance on menstrual health.
class FirstPeriodEducationScreen extends StatelessWidget {
  const FirstPeriodEducationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('First Period & Cycle Guide'),
        backgroundColor: RhythmaColors.rose,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildGuideCard(
              title: '🌸 What is a Menstrual Cycle?',
              content:
                  'A menstrual cycle is a natural, healthy monthly process where your body prepares for reproductive health. A typical cycle lasts between 21 and 35 days.',
            ),
            const SizedBox(height: 12),
            _buildGuideCard(
              title: '✨ What is Normal During Your Period?',
              content:
                  'Bleeding usually lasts 3 to 7 days. You might experience mild cramps, mood changes, or fatigue. It is completely normal for your period to be irregular during your first 2 years!',
            ),
            const SizedBox(height: 12),
            _buildGuideCard(
              title: '🩸 Hygiene & Care Basics',
              content:
                  'Change pads every 4–6 hours. Stay hydrated, eat nutritious food, and keep extra supplies in your bag so you always feel prepared and confident.',
            ),
            const SizedBox(height: 12),
            _buildGuideCard(
              title: '💆 Easy Cramp Relief Tips',
              content:
                  'Use a warm heating pad or warm water bottle on your lower belly, try light stretching, and get plenty of rest.',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGuideCard({required String title, required String content}) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: RhythmaColors.primary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              content,
              style: const TextStyle(fontSize: 14, height: 1.4, color: Colors.black87),
            ),
          ],
        ),
      ),
    );
  }
}
