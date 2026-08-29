// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Maithili (`mai`).
class AppLocalizationsMai extends AppLocalizations {
  AppLocalizationsMai([String locale = 'mai']) : super(locale);

  @override
  String get appTitle => 'Rhythma';

  @override
  String get settingsTitle => 'सेटिङ्ग्स';

  @override
  String get appPreferences => 'एप प्राथमिकतासभ';

  @override
  String get languagePreferences => 'भाषा प्राथमिकतासभ';

  @override
  String get darkMode => 'डार्क मोड';

  @override
  String get themeToggle => 'थिम टोगल';

  @override
  String get notificationsTitle => 'सूचनासभ';

  @override
  String get cycleTrackingReminders => 'साइकल ट्र्याकिङ रिमाइन्डरसभ';

  @override
  String get medicineAlerts => 'दवाइ अलर्टसभ';

  @override
  String get wellnessTips => 'स्वास्थ्य सल्लाह';

  @override
  String get securityPrivacyTitle => 'सुरक्षा आ गोपनीयता';

  @override
  String get appPermissions => 'एप अनुमतिसभ';

  @override
  String get privacyPolicy => 'गोपनीयता नीति';

  @override
  String get logOut => 'लग आउट';

  @override
  String get logoutConfirmation =>
      'की अहाँ साँचे Rhythma सँ लग आउट करए चाहैत छी?';

  @override
  String get cancel => 'रद्द करू';

  @override
  String get loggedOutSuccess => 'सफलतापूर्वक लग आउट भेल';

  @override
  String get selectLanguage => 'भाषा चुनु';

  @override
  String get langEnglish => 'English';

  @override
  String get langHindi => 'हिन्दी (Hindi)';

  @override
  String get langTamil => 'தமிழ் (Tamil)';

  @override
  String get langTelugu => 'తెలుగు (Telugu)';

  @override
  String get langMarathi => 'मराठी (Marathi)';

  @override
  String get homeGreeting => 'प्रणाम';

  @override
  String get homePhaseDesc => 'दिन 14 · ओभुलेशन चरण';

  @override
  String get homeNextPeriod => 'अगिला महिनावारी';

  @override
  String get homeDaysLabel => 'दिन';

  @override
  String get homeFertileWindow => 'फर्टाइल समय · ';

  @override
  String get homeHighEnergy => 'उच्च ऊर्जा';

  @override
  String get homeFertileWindowDisclaimer =>
      'This is an estimate based on your logged data, not medical or contraceptive advice.';

  @override
  String get homeAiTitle => 'RHYTHMA AI';

  @override
  String get homeAiSubtitle => 'अपन शरीरक बारेमे किछो पुछू,\nअपन भाषामे।';

  @override
  String get homeAiPrompt => 'हमर महिनावारी अनियमित किएक अछि?';

  @override
  String get homeFeelingTitle => 'आइज अहाँ केहन महसूस क रहल छी?';

  @override
  String get homeLogAll => 'सभ लग करू';

  @override
  String get homeLogFlow => 'प्रवाह';

  @override
  String get homeLogMood => 'मूड';

  @override
  String get homeLogSleep => 'नीन';

  @override
  String get homeLogStress => 'तनाव';

  @override
  String get homeWeeklyInsightLabel => 'साप्ताहिक जानकारी';

  @override
  String get homeWeeklyInsightTitle =>
      'एहि सप्ताहमे अहाँक नीन 12% नीक भेल अछि — अहाँक साइकल नीक भ सकैत अछि।';

  @override
  String get homeWeeklyInsightDesc =>
      'ओभुलेशन सँ पहिने लगातार आराम हर्मोनक सन्तुलनकेँ समर्थन करैत अछि।';

  @override
  String get homeLearnTitle => 'Rhythma सङ्ग सीखू';

  @override
  String get homeLearnPcos => 'PCOS बुझब';

  @override
  String get homeLearnHormones => 'हर्मोनक आधारभूत ज्ञान';

  @override
  String get homeLearnIron => 'आयरनयुक्त भोजन';

  @override
  String get homeArticle => 'लेख';

  @override
  String get homeFailedLoad => 'ड्यासबोर्ड लोड करबामे विफल';

  @override
  String get homeRetry => 'पुनः प्रयास करू';



  @override
  String get homeSleep => 'नीन';

  @override
  String get homeComingSoon => 'शीघ्र आबि रहल अछि';

  @override
  String homeUnderDevelopment(String topic) {
    return '$topic वर्तमानमे विकासक चरणमे अछि।';
  }

  @override
  String get homeErrorNetwork =>
      'कृपया अपन इन्टरनेट जडान जाँच करू आ पुनः प्रयास करू।';

  @override
  String get homeErrorAuth =>
      'अहाँक सत्र समाप्त भ गेल अछि। कृपया पुनः लग इन करू।';

  @override
  String get homeErrorServer =>
      'किछु गल्ती भेल अछि। कृपया किछु समय बाद पुनः प्रयास करू।';

  @override
  String get homeErrorGeneric =>
      'डाटा लोड करबामे असमर्थ। कृपया पुनः प्रयास करू।';

  @override
  String homeQuickLogTitle(String label) {
    return 'लग करू $label';
  }

  @override
  String homeQuickLogSaved(String label, String value) {
    return '$label लग कएल गेल: $value';
  }

  @override
  String get homePrivacySecurity => 'गोपनीयता आ सुरक्षा';

  @override
  String get homeOk => 'ठीक अछि';

  @override
  String get cycleTrackerTitle => 'साइकल ट्र्याकर';

  @override
  String get cycleToday => 'आइज';

  @override
  String get cyclePhasePeriod => 'महिनावारी';

  @override
  String get cyclePhaseFollicular => 'फोलिक्युलर';

  @override
  String get cyclePhaseOvulation => 'ओभुलेशन';

  @override
  String get cyclePhaseLuteal => 'ल्युटियल';

  @override
  String get logFor => 'क लेल लग करू';

  @override
  String get logNone => 'किछु नहि';

  @override
  String get logLight => 'हल्का';

  @override
  String get logMedium => 'मध्यम';

  @override
  String get logHeavy => 'बेसी';

  @override
  String get logEnergyLow => 'कम';

  @override
  String get logEnergyMid => 'मध्यम';

  @override
  String get logEnergyHigh => 'बेसी';

  @override
  String get logSleep1 => '<5 घण्टा';

  @override
  String get logSleep2 => '5-7 घण्टा';

  @override
  String get logSleep3 => '7-9 घण्टा';

  @override
  String get logSleep4 => '9 घण्टा+';

  @override
  String get logSympCramps => 'दर्द';

  @override
  String get logSympHeadache => 'माथ दर्द';

  @override
  String get logSympBloating => 'पेट फुलाब';

  @override
  String get logSympAcne => 'मुहाँसा';

  @override
  String get logLabelEnergy => 'ऊर्जा';

  @override
  String get logLabelSymptoms => 'लक्षणसभ';

  @override
  String get logToday => 'आइज लग करू';

  @override
  String get logTitle => 'अपन दिन लग करू';

  @override
  String get logFlowIntensity => 'प्रवाहक तीब्रता';

  @override
  String get logMood => 'मूड';

  @override
  String get logSleepHours => 'नीनक घण्टा';

  @override
  String get logStressLevel => 'तनावक स्तर';

  @override
  String get logSave => 'लग सेभ करू';

  @override
  String get logSympFatigue => 'थकान';

  @override
  String get logSympNausea => 'उल्टीक मन';

  @override
  String get logSympBackPain => 'पीठ दर्द';

  @override
  String get assistantTitle => 'Rhythma असिस्टेन्ट';

  @override
  String get assistantSubtitle => 'अहाँक व्यक्तिगत स्वास्थ्य साथी';

  @override
  String get assistantInputHint => 'अपन स्वास्थ्यक बारेमे किछो पुछू...';

  @override
  String assistantWelcome(String name) {
    return 'प्रणाम $name 🌸 हम Rhythma छी, अहाँक व्यक्तिगत स्वास्थ्य साथी। हमरासँ अपन साइकल, लक्षण वा स्वास्थ्यक बारेमे किछो पुछू।';
  }

  @override
  String get assistantSug1 => 'हमर महिनावारी अनियमित किएक अछि?';

  @override
  String get assistantSug2 => 'तेज दर्दक कारण की अछि?';

  @override
  String get assistantSug3 => 'की 35 दिनक साइकल सामान्य अछि?';

  @override
  String get assistantSug4 => 'PMS मे मदद करए बला भोजन';

  @override
  String get assistantSug5 => 'हमर महिनावारी अनियमित अछि — की ई सामान्य अछि?';

  @override
  String get assistantDisclaimer =>
      'This assistant provides general wellness information only and is not a substitute for professional medical advice.';

  @override
  String get insightsTitle => 'स्वास्थ्य जानकारी';

  @override
  String get insightsSubtitle => 'पछिला 90 दिन';



  @override
  String get insightsVar => 'साइकलक परिवर्तनशीलता';

  @override
  String get insightsAvgCycle => 'औसत साइकल';

  @override
  String get insightsRegular => 'नियमित';

  @override
  String get insightsModerate => 'मध्यम';

  @override
  String get insightsTrendLabel => 'साइकलक लम्बाइ प्रवृत्ति';

  @override
  String get insightsStabilizing => 'स्थिर भ रहल अछि';

  @override
  String get insightsHealthy => 'स्वस्थ';

  @override
  String get insightsSymptomsLabel => 'लक्षणक ढाँचा';

  @override
  String get insightsMoodSwings => 'मूड परिवर्तन';

  @override
  String get insightsWellnessLabel => 'स्वास्थ्य सिफारिससभ';

  @override
  String get insightsRec1 => 'महिनावारी शुरु होएबाक समयमे आयरनयुक्त भोजन खाऊ';

  @override
  String get insightsRec2 => 'ल्युटियल-चरणक दिनसभमे 10-मिनटक योग करू';

  @override
  String get insightsRec3 => 'ओभुलेशनक सप्ताहमे 2.5 लिटर पानि पीबू';

  @override
  String get insightsDisclaimer =>
      'These insights are based on the information you log and are intended for personal tracking only. They are not a medical diagnosis and should not replace advice from a qualified healthcare professional.';

  @override
  String get profileTitle => 'प्रोफाइल';

  @override
  String get profileYearsOld => 'वर्षक उम्र';

  @override
  String get profileCycleDay => 'साइकल दिन';

  @override
  String get profileQuickStats => 'त्वरित तथ्याङ्क';

  @override
  String get profileAvgCycleLength => 'औसत साइकल लम्बाइ';

  @override
  String get profileAvgMentalHealth => 'औसत मानसिक स्वास्थ्य';

  @override
  String get profileCycleVariability => 'साइकल परिवर्तनशीलता';

  @override
  String get profileLastCycleLength => 'पछिला साइकल लम्बाइ';

  @override
  String get profileAccountSettings => 'एकाउन्ट सेटिङ्ग्स';

  @override
  String get profileEditInfo => 'प्रोफाइल जानकारी सम्पादन करू';

  @override
  String get profileEmergencyContact => 'मेडिकल आपतकालीन सम्पर्क';

  @override
  String get profileAppSettings => 'एप सेटिङ्ग्स';

  @override
  String get profileEditProfile => 'प्रोफाइल सम्पादन करू';

  @override
  String get profileName => 'नाम';

  @override
  String get profileAge => 'उम्र';

  @override
  String get profileAvgCycleDays => 'औसत साइकल लम्बाइ (दिन)';

  @override
  String get profileSaveChanges => 'परिवर्तनसभ सेभ करू';

  @override
  String get profileNameEmptyError => 'कृपया एकटा मान्य नाम प्रविष्ट करू';

  @override
  String get profileAddContact => 'सम्पर्क जोडू';

  @override
  String get profileEditContact => 'सम्पर्क सम्पादन करू';

  @override
  String get profilePhone => 'फोन';

  @override
  String get profileSave => 'सेभ करू';

  @override
  String get profileEmergencyContactsTitle => 'आपतकालीन सम्पर्कसभ';

  @override
  String get profileAddNew => 'नया जोडू';

  @override
  String get profileNoContacts =>
      'एखन धरि कोनो आपतकालीन सम्पर्क सेट नहि कएल गेल अछि।';

  @override
  String get profileAgeInvalidError => 'कृपया एकटा मान्य उम्र प्रविष्ट करू';

  @override
  String get profileCycleInvalidError =>
      'कृपया एकटा मान्य साइकल लम्बाइ प्रविष्ट करू';

  @override
  String get profilePhoneInvalidError =>
      'कृपया एकटा मान्य फोन नम्बर प्रविष्ट करू';

  @override
  String get contactNameRequiredError => 'सम्पर्क नाम आवश्यक अछि';

  @override
  String get edit => 'सम्पादन करू';

  @override
  String get delete => 'मेटाऊ';

  @override
  String get onboardingAvatarOption => 'अवतार विकल्प';

  @override
  String get navHome => 'होम';

  @override
  String get navCycle => 'साइकल';

  @override
  String get navAsk => 'पुछू';

  @override
  String get navInsights => 'जानकारी';

  @override
  String get navYou => 'अहाँ';

  @override
  String get settingsHelpSupport => 'मद्दत आ समर्थन';

  @override
  String get settingsContactUs => 'हमरासँ सम्पर्क करू / बग रिपोर्ट करू';

  @override
  String get settingsContactDesc => 'हमर समर्थन टिमकेँ इमेल पठाऊ';

  @override
  String get settingsEmailError =>
      'इमेल एप नहि खुजि सकल। कृपया support@rhythma.com पर हमरा इमेल करू';

  @override
  String get settingsData => 'डाटा';

  @override
  String get settingsExportData => 'हमर डाटा एक्सपोर्ट करू';

  @override
  String get settingsExportDataDesc =>
      'अपन प्रोफाइल, सम्पर्क आ साइकल लग्सकेँ JSON क रूपमे डाउनलोड करू';

  @override
  String get settingsExportSuccess => 'डाटा सफलतापूर्वक एक्सपोर्ट भेल';

  @override
  String get onboardingPrivacyNote =>
      'अहाँक जानकारी अहाँक डिभाइसमे रहैत अछि। हम अहाँक अनुमति बिना अहाँक डाटा कहियो शेयर नहि करैत छी।';

  @override
  String get onboardingNext => 'अगिला';

  @override
  String get onboardingBack => 'पाछाँ';

  @override
  String get onboardingSkip => 'छोड़ू';

  @override
  String get onboardingDone => 'शुरु करू';

  @override
  String get onboardingStep1Title => 'अपन भाषा चुनु';

  @override
  String get onboardingStep1Subtitle =>
      'ओ भाषा चुनु जाहिमे अहाँ सभसँ बेसी सहज छी';

  @override
  String get onboardingStep2Title => 'अपन बारेमे बताऊ';

  @override
  String get onboardingStep2Subtitle =>
      'एहिसँ हमरा अहाँक अनुभवकेँ व्यक्तिगत बनाबएमे मद्दत भेटैत अछि';

  @override
  String get onboardingNameHint => 'अहाँक नाम वा उपनाम';

  @override
  String get onboardingNameLabel => 'नाम';

  @override
  String get onboardingAgeLabel => 'उम्र';

  @override
  String get onboardingHeightLabel => 'उँचाइ (सेमी)';

  @override
  String get onboardingWeightLabel => 'ओजन (केजी)';

  @override
  String get onboardingAvatarLabel => 'एकटा अवतार चुनु';

  @override
  String get onboardingStep3Title => 'अहाँक साइकल';

  @override
  String get onboardingStep3Subtitle =>
      'अपन साइकल बुझएमे हमर मद्दत करू — यदि सुनिश्चित नहि छी तँ छोड़ि सकैत छी';

  @override
  String get onboardingLastPeriodLabel => 'पछिला महिनावारी शुरु होएबाक तारिख';

  @override
  String get onboardingCycleLengthLabel => 'औसत साइकल लम्बाइ (दिन)';

  @override
  String get onboardingPeriodDurationLabel => 'औसत महिनावारीक अवधि (दिन)';

  @override
  String get onboardingCycleRegularityLabel => 'साइकलक नियमितता';

  @override
  String get onboardingRegular => 'नियमित';

  @override
  String get onboardingIrregular => 'अनियमित';

  @override
  String get onboardingStep4Title => 'किछु आओर (वैकल्पिक)';

  @override
  String get onboardingStep4Subtitle =>
      'क्षेत्र-विशिष्ट स्वास्थ्य सल्लाह सिफारिस करएमे हमरा मद्दत करैत अछि';

  @override
  String get onboardingPhoneLabel => 'फोन नम्बर (वैकल्पिक)';

  @override
  String get onboardingPhoneHint => 'जहिना +919876543210';

  @override
  String get onboardingCityLabel => 'शहर (वैकल्पिक)';

  @override
  String get onboardingStateLabel => 'राज्य / पिन कोड (वैकल्पिक)';

  @override
  String get onboardingStep5Title => 'अपडेट रहू';

  @override
  String get onboardingStep5Subtitle =>
      'सूचनासभ सक्षम करू जाहिसँ Rhythma अहाँकेँ सही समयमे मोन पाड़ि सकए';

  @override
  String get onboardingEnableNotifications => 'साइकल रिमाइन्डरसभ सक्षम करू';

  @override
  String get onboardingNotificationsDesc =>
      'अपन महिनावारी आ ओभुलेशन विन्डो सँ पहिने हल्का रिमाइन्डर प्राप्त करू';

  @override
  String get onboardingDataConsentLabel =>
      'हम एहि डिभाइसमे अपन स्वास्थ्य डाटा स्थानीय रूपसँ भण्डारण करबाक लेल सहमति दैत छी';

  @override
  String get onboardingDataConsentRequired =>
      'जारी रखबाक लेल कृपया स्वीकार करू';

  @override
  String get onboardingNameRequired => 'कृपया अपन नाम प्रविष्ट करू';

  @override
  String get onboardingAgeInvalid =>
      'कृपया एकटा मान्य उम्र प्रविष्ट करू (10-120)';

  @override
  String get onboardingHeightInvalid =>
      'कृपया एकटा मान्य उँचाइ प्रविष्ट करू (50-250 सेमी)';

  @override
  String get onboardingWeightInvalid =>
      'कृपया एकटा मान्य ओजन प्रविष्ट करू (20-300 केजी)';

  @override
  String get onboardingPhoneInvalid =>
      'अन्तर्राष्ट्रिय ढाँचाक उपयोग करू, जहिना +919876543210';

  @override
  String get onboardingTapToSelectDate => 'तारिख चुनबाक लेल ट्याप करू';

  @override
  String get langGujarati => 'ગુજરાતી (Gujarati)';

  @override
  String get deleteAccount => 'एकाउन्ट मेटाऊ';

  @override
  String get deleteAccountConfirmationDesc =>
      'ई कार्य स्थायी अछि आ एकरा वापस नहि लेल जा सकैत अछि। अहाँक सभ डाटा मेटा देल जाएत।';

  @override
  String get accountDeletedSuccess => 'एकाउन्ट सफलतापूर्वक मेटाएल गेल।';

  @override
  String get smsErrorGeneric => 'किछु गल्ती भेल अछि। कृपया पुनः प्रयास करू।';

  @override
  String get smsErrorEnterPhone => 'कृपया एकटा फोन नम्बर प्रविष्ट करू';

  @override
  String get smsErrorInvalidPhone =>
      'अन्तर्राष्ट्रिय ढाँचामे एकटा मान्य फोन नम्बर प्रविष्ट करू, जहिना +919876543210';

  @override
  String get smsSuccessSaved => 'SMS सेटिङ्ग्स सफलतापूर्वक सेभ भेल!';

  @override
  String get smsErrorAddPhoneFirst => 'पहिने एकटा फोन नम्बर जोडू आ सेभ करू';

  @override
  String get smsSummaryMessage =>
      '🌸 Rhythma स्वास्थ्य सारांश\nई Rhythma सँ अहाँक अन-डिमान्ड सारांश अछि।\nअपन नवीनतम साइकल जानकारीक लेल एप खोलू।\nअनसब्सक्राइब करबाक लेल STOP क रिप्लाइ करू।';

  @override
  String get smsSuccessSent => 'अहाँक फोनमे सारांश पठाएल गेल!';

  @override
  String get smsErrorRateLimit =>
      'अहाँ प्रति मिनट एकटा सारांश पठा सकैत छी, कृपया किछु समय प्रतीक्षा करू आ पुनः प्रयास करू।';

  @override
  String get smsErrorSessionExpired =>
      'अहाँक सत्र समाप्त भ गेल अछि। कृपया पुनः लग इन करू।';

  @override
  String get smsErrorNetwork =>
      'सर्भर सँग जडान नहि भ सकल। अपन जडान जाँच करू आ पुनः प्रयास करू।';

  @override
  String get smsScreenTitle => 'SMS सारांशसभ';

  @override
  String get smsScreenSubtitle => 'एप बिना सेहो अपडेट रहू';

  @override
  String get smsInfoCardTitle => 'साप्ताहिक स्वास्थ्य सारांश';

  @override
  String get smsInfoCardBody =>
      'प्रत्येक सप्ताह, Rhythma अहाँकेँ अहाँक साइकलक स्थिति, स्वास्थ्य स्कोर आ कोनो महत्त्वपूर्ण ढाँचाक एकटा संक्षिप्त सारांश SMS क माध्यमसँ सिधा अहाँक फोनमे पठाओत। ई डाटा वा एप बिना काज करैत अछि।';

  @override
  String get smsConfigTitle => 'कन्फिगरेसन';

  @override
  String get smsPhoneLabel => 'फोन नम्बर';

  @override
  String get smsPhoneHint => '+91 98765 43210';

  @override
  String get smsEnableWeekly => 'साप्ताहिक SMS सक्षम करू';

  @override
  String get smsSaveSettings => 'सेटिङ्ग्स सेभ करू';

  @override
  String get smsSendSectionTitle => 'एखने एकटा सारांश पठाऊ';

  @override
  String get smsSendRecipientPrefix => 'नीचाँ देल गेल म्यासेज पठाबैत अछि:';

  @override
  String get smsSendNoPhone => 'पहिने ऊपर एकटा फोन नम्बर जोडू आ सेभ करू।';

  @override
  String get smsSendButton => 'एखने सारांश पठाऊ';

  @override
  String get insightsNotEnoughData =>
      'अपन सम्पूर्ण स्वास्थ्य जानकारी अनलक करबाक लेल साइकल ट्याबमे आओर किछु साइकल लग करू।';

  @override
  String get insightsNoSymptomsYet =>
      'एखन धरि कोनो लक्षण लग नहि कएल गेल अछि — एतय ढाँचासभ देखबाक लेल साइकल ट्याबमे किछु लग करू।';

  @override
  String get insightsNotEnoughTrendData =>
      'एतय अपन प्रवृत्ति देखबाक लेल कम सँ कम दुटा साइकल लग करू।';

  @override
  String insightsLoadError(String error) {
    return 'अहाँक जानकारी लोड नहि कएल जा सकल: $error';
  }

  @override
  String get assistantAccessibilitySuggestedPrompt => 'सुझाएल गेल प्रम्प्ट';

  @override
  String get assistantAccessibilityMessageInput => 'म्यासेज इनपुट';

  @override
  String get assistantAccessibilityMessageInputHint =>
      'अपन प्रश्न एतय टाइप करू';

  @override
  String get assistantAccessibilitySendMessage => 'म्यासेज पठाऊ';

  @override
  String get assistantAccessibilitySendMessageHint =>
      'अहाँक म्यासेज असिस्टेन्टकेँ पठाबैत अछि';

  @override
  String get assistantAccessibilityTyping => 'असिस्टेन्ट टाइप क रहल अछि';

  @override
  String get languageSelectionError =>
      'भाषा सेभ करबामे असमर्थ। कृपया पुनः प्रयास करू।';

  @override
  String get pleaseEnterPhoneNumber => 'Please enter phone number';

  @override
  String get pleaseEnterValidPhoneNumber => 'Please enter valid phone number';

  @override
  String get verificationFailed => 'Verification failed';

  @override
  String otpSentTo(String phone) {
    return 'OTP sent to $phone';
  }

  @override
  String get pleaseEnterOtp => 'Please enter OTP';

  @override
  String get invalidOtp => 'Invalid OTP';

  @override
  String get failedToGetIdToken => 'Failed to get ID token';

  @override
  String get welcomeToRhythma => 'Welcome to Rhythma';

  @override
  String get enterOtpSentToPhone => 'Enter OTP sent to phone';

  @override
  String get loginOrSignUpWithPhone => 'Login or Sign up with phone';

  @override
  String get phoneNumber => 'Phone number';

  @override
  String get sendingOtp => 'Sending OTP...';

  @override
  String get getOtp => 'Get OTP';

  @override
  String get otp => 'OTP';

  @override
  String get verifying => 'Verifying...';

  @override
  String get verifyOtp => 'Verify OTP';

  @override
  String get useDifferentPhoneNumber => 'Use different phone number';

  @override
  String get nudgeCompleteProfileTitle => 'आओर सटीक भविष्यवाणी चाहैत छी?';

  @override
  String get nudgeCompleteProfileBody =>
      'साइकल भविष्यवाणीसभकेँ बेहतर बनेबाक लेल अपन पछिला महिनावारी शुरु होएबाक सही तारिख जोडू।';

  @override
  String get nudgeCompleteProfileAction => 'अपडेट करू';

  @override
  String get nudgeCompleteProfileDismiss => 'शायद बादमे';

  @override
  String get cycleHistory => 'Cycle History';

  @override
  String get noLogsYet => 'No logs yet';

  @override
  String get dayCycle => 'Day cycle';

  @override
  String get ayurvedaWellnessTitle => 'Ayurveda-inspired wellness';

  @override
  String get ayurvedaDisclaimer =>
      'Educational information only. Ayurveda-inspired content is not medical advice, diagnosis, or treatment.';

  @override
  String get ayurvedaMenstrualTitle => 'Rest and reflection';

  @override
  String get ayurvedaMenstrualDescription =>
      'Ayurvedic traditions describe menstruation as a time that may be associated with rest, reflection, and gentle self-care.';

  @override
  String get ayurvedaFollicularTitle => 'Renewal and activity';

  @override
  String get ayurvedaFollicularDescription =>
      'Ayurvedic wellness traditions associate the post-menstrual period with renewal and gradually increasing activity.';

  @override
  String get ayurvedaOvulationTitle => 'Connection and balance';

  @override
  String get ayurvedaOvulationDescription =>
      'Some Ayurvedic traditions describe the middle of the cycle as a time associated with vitality and social connection.';

  @override
  String get ayurvedaLutealTitle => 'Grounding and routine';

  @override
  String get ayurvedaLutealDescription =>
      'Ayurvedic wellness traditions emphasize maintaining a calm routine and mindful self-care during the later part of the cycle.';

  @override
  String get logFlowVeryHeavy => 'Very Heavy';

  @override
  String get logFlowSpotting => 'Spotting';

  @override
  String get logSympSeverePain => 'Severe Pain';

  @override
  String get logSympFainting => 'Fainting';

  @override
  String get ayurvedaWellnessTitle => 'Ayurveda-inspired wellness';

  @override
  String get ayurvedaDisclaimer => 'Educational information only. Ayurveda-inspired content is not medical advice, diagnosis, or treatment.';

  @override
  String get ayurvedaMenstrualTitle => 'Rest and reflection';

  @override
  String get ayurvedaMenstrualDescription => 'Ayurvedic traditions describe menstruation as a time that may be associated with rest, reflection, and gentle self-care.';

  @override
  String get ayurvedaFollicularTitle => 'Renewal and activity';

  @override
  String get ayurvedaFollicularDescription => 'Ayurvedic wellness traditions associate the post-menstrual period with renewal and gradually increasing activity.';

  @override
  String get ayurvedaOvulationTitle => 'Connection and balance';

  @override
  String get ayurvedaOvulationDescription => 'Some Ayurvedic traditions describe the middle of the cycle as a time associated with vitality and social connection.';

  @override
  String get ayurvedaLutealTitle => 'Grounding and routine';

  @override
  String get ayurvedaLutealDescription => 'Ayurvedic wellness traditions emphasize maintaining a calm routine and mindful self-care during the later part of the cycle.';
}
