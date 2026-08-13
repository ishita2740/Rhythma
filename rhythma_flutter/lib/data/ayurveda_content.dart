class AyurvedaContent {
  final String titleKey;
  final String descriptionKey;

  const AyurvedaContent({
    required this.titleKey,
    required this.descriptionKey,
  });
}

const String ayurvedaDisclaimerKey = 'ayurvedaDisclaimer';
const String ayurvedaWellnessTitleKey = 'ayurvedaWellnessTitle';

const Map<String, List<AyurvedaContent>> ayurvedaContent = {
  'menstrual': [
    AyurvedaContent(
      titleKey: 'ayurvedaMenstrualTitle',
      descriptionKey: 'ayurvedaMenstrualDescription',
    ),
  ],
  'follicular': [
    AyurvedaContent(
      titleKey: 'ayurvedaFollicularTitle',
      descriptionKey: 'ayurvedaFollicularDescription',
    ),
  ],
  'ovulation': [
    AyurvedaContent(
      titleKey: 'ayurvedaOvulationTitle',
      descriptionKey: 'ayurvedaOvulationDescription',
    ),
  ],
  'luteal': [
    AyurvedaContent(
      titleKey: 'ayurvedaLutealTitle',
      descriptionKey: 'ayurvedaLutealDescription',
    ),
  ],
};