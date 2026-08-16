// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Nepali (`ne`).
class AppLocalizationsNe extends AppLocalizations {
  AppLocalizationsNe([String locale = 'ne']) : super(locale);

  @override
  String get appTitle => 'Rhythma';

  @override
  String get settingsTitle => 'सेटिङहरू';

  @override
  String get appPreferences => 'एप प्राथमिकताहरू';

  @override
  String get languagePreferences => 'भाषा प्राथमिकताहरू';

  @override
  String get darkMode => 'डार्क मोड';

  @override
  String get themeToggle => 'थिम टगल';

  @override
  String get notificationsTitle => 'सूचनाहरू';

  @override
  String get cycleTrackingReminders => 'साइकल ट्र्याकिङ रिमाइन्डरहरू';

  @override
  String get medicineAlerts => 'औषधि अलर्टहरू';

  @override
  String get wellnessTips => 'स्वास्थ्य सुझावहरू';

  @override
  String get securityPrivacyTitle => 'सुरक्षा र गोपनीयता';

  @override
  String get appPermissions => 'एप अनुमतिहरू';

  @override
  String get privacyPolicy => 'गोपनीयता नीति';

  @override
  String get logOut => 'लग आउट';

  @override
  String get logoutConfirmation => 'के तपाईं साँच्चै Rhythma बाट लग आउट गर्न चाहनुहुन्छ?';

  @override
  String get cancel => 'रद्द गर्नुहोस्';

  @override
  String get loggedOutSuccess => 'सफलतापूर्वक लग आउट गरियो';

  @override
  String get selectLanguage => 'भाषा छान्नुहोस्';

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
  String get homeGreeting => 'नमस्ते';

  @override
  String get homePhaseDesc => 'दिन १४ · ओभ्युलेसन चरण';

  @override
  String get homeNextPeriod => 'अर्को महिनावारी';

  @override
  String get homeDaysLabel => 'दिन';

  @override
  String get homeFertileWindow => 'प्रजनन विन्डो · ';

  @override
  String get homeHighEnergy => 'उच्च ऊर्जा';

  @override
  String get homeFertileWindowDisclaimer =>
      'This is an estimate based on your logged data, not medical or contraceptive advice.';

  @override
  String get homeAiTitle => 'RHYTHMA AI';

  @override
  String get homeAiSubtitle => 'तपाईंको शरीरको बारेमा केहि पनि सोध्नुहोस्,\nतपाईंको आफ्नै भाषामा।';

  @override
  String get homeAiPrompt => 'मेरो महिनावारी किन अनियमित छ?';

  @override
  String get homeFeelingTitle => 'आज कस्तो महसुस गर्दै हुनुहुन्छ?';

  @override
  String get homeLogAll => 'सबै लग गर्नुहोस्';

  @override
  String get homeLogFlow => 'प्रवाह';

  @override
  String get homeLogMood => 'मूड';

  @override
  String get homeLogSleep => 'निद्रा';

  @override
  String get homeLogStress => 'तनाव';

  @override
  String get homeWeeklyInsightLabel => 'साप्ताहिक इनसाइट';

  @override
  String get homeWeeklyInsightTitle => 'यस हप्ता तपाईंको निद्रामा १२% ले सुधार आयो - तपाईंको साइकलले तपाईंलाई धन्यवाद दिन सक्छ।';

  @override
  String get homeWeeklyInsightDesc => 'ओभ्युलेसन अघि निरन्तर आरामले हर्मोन सन्तुलन कायम राख्न मद्दत गर्दछ।';

  @override
  String get homeLearnTitle => 'Rhythma सँग सिक्नुहोस्';

  @override
  String get homeLearnPcos => 'PCOS बुझ्दै';

  @override
  String get homeLearnHormones => 'हर्मोन आधारभूत कुराहरू';

  @override
  String get homeLearnIron => 'फलाम युक्त खाना';

  @override
  String get homeArticle => 'लेख';

  @override
  String get homeFailedLoad => 'ड्यासबोर्ड लोड गर्न असफल';

  @override
  String get homeRetry => 'फेरि प्रयास गर्नुहोस्';

  @override
  String get homeMhs => 'MHS';

  @override
  String get homeCvi => 'CVI';

  @override
  String get homeSleep => 'निद्रा';

  @override
  String get homeComingSoon => 'चाँडै आउँदैछ';

  @override
  String homeUnderDevelopment(String topic) {
    return '\$\\1 हाल विकासको क्रममा छ।';
  }

  @override
  String get homeErrorNetwork => 'कृपया आफ्नो इन्टरनेट जडान जाँच गर्नुहोस् र फेरि प्रयास गर्नुहोस्।';

  @override
  String get homeErrorAuth => 'तपाईंको सत्र समाप्त भएको छ। कृपया फेरि लग इन गर्नुहोस्।';

  @override
  String get homeErrorServer => 'केहि गलत भयो। कृपया पछि फेरि प्रयास गर्नुहोस्।';

  @override
  String get homeErrorGeneric => 'डाटा लोड गर्न असफल। कृपया फेरि प्रयास गर्नुहोस्।';

  @override
  String homeQuickLogTitle(String label) {
    return '\$\\1 लग गर्नुहोस्';
  }

  @override
  String homeQuickLogSaved(String label, String value) {
    return '\$\\1 लग गरियो: \$\\1';
  }

  @override
  String get homePrivacySecurity => 'गोपनीयता र सुरक्षा';

  @override
  String get homeOk => 'ठिक छ';

  @override
  String get cycleTrackerTitle => 'साइकल ट्रयाकर';

  @override
  String get cycleToday => 'आज';

  @override
  String get cyclePhasePeriod => 'महिनावारी';

  @override
  String get cyclePhaseFollicular => 'फोलिकुलर';

  @override
  String get cyclePhaseOvulation => 'ओभ्युलेसन';

  @override
  String get cyclePhaseLuteal => 'ल्युटियल';

  @override
  String get logFor => 'को लागि लग गर्नुहोस्';

  @override
  String get logNone => 'केहि छैन';

  @override
  String get logLight => 'हल्का';

  @override
  String get logMedium => 'मध्यम';

  @override
  String get logHeavy => 'भारी';

  @override
  String get logEnergyLow => 'कम';

  @override
  String get logEnergyMid => 'मध्यम';

  @override
  String get logEnergyHigh => 'उच्च';

  @override
  String get logSleep1 => '<५ घन्टा';

  @override
  String get logSleep2 => '५-७ घन्टा';

  @override
  String get logSleep3 => '७-९ घन्टा';

  @override
  String get logSleep4 => '९ घन्टा+';

  @override
  String get logSympCramps => 'दुखाइ';

  @override
  String get logSympHeadache => 'टाउको दुखाइ';

  @override
  String get logSympBloating => 'पेट फुल्ने';

  @override
  String get logSympAcne => 'अनुहारमा दाग';

  @override
  String get logLabelEnergy => 'ऊर्जा';

  @override
  String get logLabelSymptoms => 'लक्षणहरू';

  @override
  String get logToday => 'आज लग गर्नुहोस्';

  @override
  String get logTitle => 'तपाईंको दिन लग गर्नुहोस्';

  @override
  String get logFlowIntensity => 'प्रवाह तीव्रता';

  @override
  String get logMood => 'मूड';

  @override
  String get logSleepHours => 'निद्रा घण्टा';

  @override
  String get logStressLevel => 'तनाव स्तर';

  @override
  String get logSave => 'लग बचत गर्नुहोस्';

  @override
  String get logSympFatigue => 'थकान';

  @override
  String get logSympNausea => 'वाकवाकी';

  @override
  String get logSympBackPain => 'ढाड दुखाइ';

  @override
  String get assistantTitle => 'Rhythma सहायक';

  @override
  String get assistantSubtitle => 'तपाईंको व्यक्तिगत स्वास्थ्य साथी';

  @override
  String get assistantInputHint => 'आफ्नो स्वास्थ्यको बारेमा केहि पनि सोध्नुहोस्...';

  @override
  String assistantWelcome(String name) {
    return 'नमस्ते \$\\1 🌸 म Rhythma हुँ, तपाईंको व्यक्तिगत स्वास्थ्य साथी। मलाई तपाईंको साइकल, लक्षणहरू, वा स्वास्थ्यको बारेमा केहि पनि सोध्नुहोस्।';
  }

  @override
  String get assistantSug1 => 'मेरो महिनावारी किन अनियमित छ?';

  @override
  String get assistantSug2 => 'गम्भीर दुखाइको कारण के हो?';

  @override
  String get assistantSug3 => 'के ३५-दिने साइकल सामान्य हो?';

  @override
  String get assistantSug4 => 'PMS मा मद्दत गर्ने खानाहरू';

  @override
  String get assistantSug5 => 'मेरो महिनावारी अनियमित छ - के यो सामान्य हो?';

  @override
  String get assistantDisclaimer =>
      'This assistant provides general wellness information only and is not a substitute for professional medical advice.';

  @override
  String get insightsTitle => 'स्वास्थ्य इनसाइटहरू';

  @override
  String get insightsSubtitle => 'पछिल्लो ९० दिन';

  @override
  String get insightsMhsLabel => 'महिनावारी स्वास्थ्य स्कोर';

  @override
  String get insightsMhsDelta => 'पछिल्लो साइकलको तुलनामा +६';

  @override
  String get insightsVar => 'साइकल परिवर्तनशीलता';

  @override
  String get insightsAvgCycle => 'औसत साइकल';

  @override
  String get insightsRegular => 'नियमित';

  @override
  String get insightsModerate => 'मध्यम';

  @override
  String get insightsTrendLabel => 'साइकल लम्बाइ प्रवृत्ति';

  @override
  String get insightsStabilizing => 'स्थिर हुँदैछ';

  @override
  String get insightsHealthy => 'स्वस्थ';

  @override
  String get insightsSymptomsLabel => 'लक्षण ढाँचाहरू';

  @override
  String get insightsMoodSwings => 'मूड स्विङ्स';

  @override
  String get insightsWellnessLabel => 'स्वास्थ्य सिफारिस';

  @override
  String get insightsRec1 => 'तपाईंको महिनावारी नजिकिँदै गर्दा फलाम युक्त खाना खानुहोस्';

  @override
  String get insightsRec2 => 'तपाईंको ल्युटियल-चरण दिनहरूमा १०-मिनेट योग गर्ने प्रयास गर्नुहोस्';

  @override
  String get insightsRec3 => 'तपाईंको ओभ्युलेसन हप्ताको समयमा २.५ लिटर पानी पिउनुहोस्';

  @override
  String get insightsDisclaimer =>
      'These insights are based on the information you log and are intended for personal tracking only. They are not a medical diagnosis and should not replace advice from a qualified healthcare professional.';

  @override
  String get profileTitle => 'प्रोफाइल';

  @override
  String get profileYearsOld => 'वर्ष उमेर';

  @override
  String get profileCycleDay => 'साइकल दिन';

  @override
  String get profileQuickStats => 'द्रुत तथ्याङ्क';

  @override
  String get profileAvgCycleLength => 'औसत साइकल लम्बाइ';

  @override
  String get profileAvgMentalHealth => 'औसत मानसिक स्वास्थ्य';

  @override
  String get profileCycleVariability => 'साइकल परिवर्तनशीलता';

  @override
  String get profileLastCycleLength => 'पछिल्लो साइकल लम्बाइ';

  @override
  String get profileAccountSettings => 'खाता सेटिङहरू';

  @override
  String get profileEditInfo => 'प्रोफाइल जानकारी सम्पादन गर्नुहोस्';

  @override
  String get profileEmergencyContact => 'चिकित्सा आपतकालीन सम्पर्क';

  @override
  String get profileAppSettings => 'एप सेटिङहरू';

  @override
  String get profileEditProfile => 'प्रोफाइल सम्पादन गर्नुहोस्';

  @override
  String get profileName => 'नाम';

  @override
  String get profileAge => 'उमेर';

  @override
  String get profileAvgCycleDays => 'औसत साइकल लम्बाइ (दिन)';

  @override
  String get profileSaveChanges => 'परिवर्तनहरू बचत गर्नुहोस्';

  @override
  String get profileNameEmptyError => 'कृपया मान्य नाम प्रविष्ट गर्नुहोस्';

  @override
  String get profileAddContact => 'सम्पर्क थप्नुहोस्';

  @override
  String get profileEditContact => 'सम्पर्क सम्पादन गर्नुहोस्';

  @override
  String get profilePhone => 'फोन';

  @override
  String get profileSave => 'बचत गर्नुहोस्';

  @override
  String get profileEmergencyContactsTitle => 'आपतकालीन सम्पर्कहरू';

  @override
  String get profileAddNew => 'नयाँ थप्नुहोस्';

  @override
  String get profileNoContacts => 'अहिलेसम्म कुनै आपतकालीन सम्पर्कहरू सेट गरिएको छैन।';

  @override
  String get profileAgeInvalidError => 'कृपया मान्य उमेर प्रविष्ट गर्नुहोस्';

  @override
  String get profileCycleInvalidError => 'कृपया मान्य साइकल लम्बाइ प्रविष्ट गर्नुहोस्';

  @override
  String get profilePhoneInvalidError => 'कृपया मान्य फोन नम्बर प्रविष्ट गर्नुहोस्';

  @override
  String get contactNameRequiredError => 'सम्पर्क नाम आवश्यक छ';

  @override
  String get edit => 'सम्पादन';

  @override
  String get delete => 'मेटाउनुहोस्';

  @override
  String get onboardingAvatarOption => 'अवतार विकल्प';

  @override
  String get navHome => 'होम';

  @override
  String get navCycle => 'साइकल';

  @override
  String get navAsk => 'सोध्नुहोस्';

  @override
  String get navInsights => 'इनसाइटहरू';

  @override
  String get navYou => 'तपाईं';

  @override
  String get settingsHelpSupport => 'मद्दत र समर्थन';

  @override
  String get settingsContactUs => 'हामीलाई सम्पर्क गर्नुहोस् / बग रिपोर्ट गर्नुहोस्';

  @override
  String get settingsContactDesc => 'हाम्रो समर्थन टोलीलाई इमेल पठाउनुहोस्';

  @override
  String get settingsEmailError => 'इमेल एप खोल्न सकिएन। कृपया support@rhythma.com मा हामीलाई इमेल गर्नुहोस्';

  @override
  String get settingsData => 'डाटा';

  @override
  String get settingsExportData => 'मेरो डाटा निर्यात गर्नुहोस्';

  @override
  String get settingsExportDataDesc => 'तपाईंको प्रोफाइल, सम्पर्कहरू, र साइकल लगहरू JSON को रूपमा डाउनलोड गर्नुहोस्';

  @override
  String get settingsExportSuccess => 'डाटा सफलतापूर्वक निर्यात गरियो';

  @override
  String get onboardingPrivacyNote => 'तपाईंको जानकारी तपाईंको उपकरणमा रहन्छ। हामी तपाईंको अनुमति बिना कहिल्यै तपाईंको डाटा साझा गर्दैनौं।';

  @override
  String get onboardingNext => 'अर्को';

  @override
  String get onboardingBack => 'पछाडि';

  @override
  String get onboardingSkip => 'छोड्नुहोस्';

  @override
  String get onboardingDone => 'सुरु गरौं';

  @override
  String get onboardingStep1Title => 'आफ्नो भाषा छान्नुहोस्';

  @override
  String get onboardingStep1Subtitle => 'कुन भाषा तपाईंको लागि सबैभन्दा सहज छ';

  @override
  String get onboardingStep2Title => 'आफ्नो बारेमा बताउनुहोस्';

  @override
  String get onboardingStep2Subtitle => 'यसले हामीलाई तपाईंको अनुभव व्यक्तिगत बनाउन मद्दत गर्दछ';

  @override
  String get onboardingNameHint => 'तपाईंको नाम वा उपनाम';

  @override
  String get onboardingNameLabel => 'नाम';

  @override
  String get onboardingAgeLabel => 'उमेर';

  @override
  String get onboardingHeightLabel => 'उचाइ (सेमी)';

  @override
  String get onboardingWeightLabel => 'तौल (किग्रा)';

  @override
  String get onboardingAvatarLabel => 'अवतार छान्नुहोस्';

  @override
  String get onboardingStep3Title => 'तपाईंको साइकल';

  @override
  String get onboardingStep3Subtitle => 'हामीलाई तपाईंको साइकल बुझ्न मद्दत गर्नुहोस् - निश्चित हुनुहुन्न भने छोड्न सक्नुहुन्छ';

  @override
  String get onboardingLastPeriodLabel => 'पछिल्लो महिनावारी सुरु मिति';

  @override
  String get onboardingCycleLengthLabel => 'औसत साइकल लम्बाइ (दिन)';

  @override
  String get onboardingPeriodDurationLabel => 'औसत महिनावारी अवधि (दिन)';

  @override
  String get onboardingCycleRegularityLabel => 'साइकल नियमितता';

  @override
  String get onboardingRegular => 'नियमित';

  @override
  String get onboardingIrregular => 'अनियमित';

  @override
  String get onboardingStep4Title => 'थोरै थप (वैकल्पिक)';

  @override
  String get onboardingStep4Subtitle => 'स्थान-विशिष्ट स्वास्थ्य सुझावहरू प्रदान गर्न मद्दत गर्दछ';

  @override
  String get onboardingPhoneLabel => 'फोन नम्बर (वैकल्पिक)';

  @override
  String get onboardingPhoneHint => 'जस्तै +919876543210';

  @override
  String get onboardingCityLabel => 'शहर (वैकल्पिक)';

  @override
  String get onboardingStateLabel => 'राज्य / पिन कोड (वैकल्पिक)';

  @override
  String get onboardingStep5Title => 'अद्यावधिक रहनुहोस्';

  @override
  String get onboardingStep5Subtitle => 'Rhythma ले तपाईंलाई समयमै रिमाइन्डरहरू दिन सकोस् भनेर सूचनाहरू सक्षम गर्नुहोस्';

  @override
  String get onboardingEnableNotifications => 'साइकल रिमाइन्डरहरू सक्षम गर्नुहोस्';

  @override
  String get onboardingNotificationsDesc => 'तपाईंको महिनावारी र ओभ्युलेसन विन्डो अघि कोमल रिमाइन्डरहरू प्राप्त गर्नुहोस्';

  @override
  String get onboardingDataConsentLabel => 'म यस उपकरणमा मेरो स्वास्थ्य डाटा सुरक्षित भण्डारण गर्न सहमत छु';

  @override
  String get onboardingDataConsentRequired => 'जारी राख्न कृपया सहमत हुनुहोस्';

  @override
  String get onboardingNameRequired => 'कृपया आफ्नो नाम प्रविष्ट गर्नुहोस्';

  @override
  String get onboardingAgeInvalid => 'कृपया मान्य उमेर प्रविष्ट गर्नुहोस् (१०-१२०)';

  @override
  String get onboardingHeightInvalid => 'कृपया मान्य उचाइ प्रविष्ट गर्नुहोस् (५०-२५० सेमी)';

  @override
  String get onboardingWeightInvalid => 'कृपया मान्य तौल प्रविष्ट गर्नुहोस् (२०-३०० किग्रा)';

  @override
  String get onboardingPhoneInvalid => 'अन्तर्राष्ट्रिय ढाँचा प्रयोग गर्नुहोस्, जस्तै +919876543210';

  @override
  String get onboardingAgeRequired => 'कृपया आफ्नो उमेर प्रविष्ट गर्नुहोस् वा दायरा चयन गर्नुहोस्';

  @override
  String get onboardingHeightRequired => 'कृपया आफ्नो उचाइ प्रविष्ट गर्नुहोस् वा दायरा चयन गर्नुहोस्';

  @override
  String get onboardingWeightRequired => 'कृपया आफ्नो तौल प्रविष्ट गर्नुहोस् वा दायरा चयन गर्नुहोस्';

  @override
  String get onboardingNotSure => 'निश्चित छैन';

  @override
  String get onboardingApproximate => 'अनुमानित';

  @override
  String get onboardingAgeHint => 'आफ्नो उमेर प्रविष्ट गर्नुहोस्';

  @override
  String get onboardingAgeUnit => 'वर्ष';

  @override
  String get onboardingHeightHint => 'आफ्नो उचाइ प्रविष्ट गर्नुहोस्';

  @override
  String get onboardingHeightUnit => 'सेमी';

  @override
  String get onboardingWeightHint => 'आफ्नो तौल प्रविष्ट गर्नुहोस्';

  @override
  String get onboardingWeightUnit => 'किग्रा';

  @override
  String get onboardingRangeUnder18 => '१८ मुनि';

  @override
  String get onboardingRange18to25 => '१८-२५';

  @override
  String get onboardingRange26to35 => '२६-३५';

  @override
  String get onboardingRange36to50 => '३६-५०';

  @override
  String get onboardingRange51to65 => '५१-६५';

  @override
  String get onboardingRangeOver65 => '६५ माथि';

  @override
  String get onboardingRangeUnder150 => '१५० सेमी मुनि';

  @override
  String get onboardingRange150to160 => '१५०-१६० सेमी';

  @override
  String get onboardingRange161to170 => '१६१-१७० सेमी';

  @override
  String get onboardingRange171to180 => '१७१-१८० सेमी';

  @override
  String get onboardingRangeOver180 => '१८० सेमी माथि';

  @override
  String get onboardingRangeUnder50kg => '५० किग्रा मुनि';

  @override
  String get onboardingRange50to65kg => '५०-६५ किग्रा';

  @override
  String get onboardingRange66to80kg => '६६-८० किग्रा';

  @override
  String get onboardingRange81to100kg => '८१-१०० किग्रा';

  @override
  String get onboardingRangeOver100kg => '१०० किग्रा माथि';

  @override
  String get onboardingTapToSelectDate => 'मिति चयन गर्न ट्याप गर्नुहोस्';

  @override
  String get onboardingDays => 'दिन';

  @override
  String get onboardingApproximateLabel => 'तपाईंको पछिल्लो महिनावारी कहिले थियो?';

  @override
  String get onboardingApproximateLessWeek => '१ हप्ता भन्दा कम अघि';

  @override
  String get onboardingApproximate1to2Weeks => '१-२ हप्ता अघि';

  @override
  String get onboardingApproximate3to4Weeks => '३-४ हप्ता अघि';

  @override
  String get onboardingApproximateMoreMonth => '१ महिना भन्दा बढी अघि';

  @override
  String get onboardingPickExactDate => 'यसको सट्टा सही मिति छान्नुहोस्';

  @override
  String get onboardingLastPeriodRequired => 'कृपया तपाईंको पछिल्लो महिनावारी कहिले थियो चयन गर्नुहोस्';

  @override
  String get nudgeCompleteProfileTitle => 'थप सही भविष्यवाणीहरू चाहनुहुन्छ?';

  @override
  String get nudgeCompleteProfileBody => 'साइकल भविष्यवाणीहरू सुधार गर्न तपाईंको पछिल्लो महिनावारीको सही सुरु मिति थप्नुहोस्।';

  @override
  String get nudgeCompleteProfileAction => 'अद्यावधिक गर्नुहोस्';

  @override
  String get nudgeCompleteProfileDismiss => 'पछि';

  @override
  String get smsScreenTitle => 'SMS सारांशहरू';

  @override
  String get smsScreenSubtitle => 'एप बिना पनि अद्यावधिक रहनुहोस्';

  @override
  String get smsInfoCardTitle => 'साप्ताहिक स्वास्थ्य सारांश';

  @override
  String get smsInfoCardBody => 'हरेक हप्ता, Rhythma ले तपाईंलाई तपाईंको साइकल स्थिति, स्वास्थ्य स्कोर, र कुनै पनि महत्त्वपूर्ण ढाँचाहरूको संक्षिप्त सारांश SMS मार्फत तपाईंको फोनमा पठाउनेछ। डाटा वा एप बिना काम गर्दछ।';

  @override
  String get smsConfigTitle => 'कन्फिगरेसन';

  @override
  String get smsPhoneLabel => 'फोन नम्बर';

  @override
  String get smsPhoneHint => '+91 98765 43210';

  @override
  String get smsEnableWeekly => 'साप्ताहिक SMS सक्षम गर्नुहोस्';

  @override
  String get smsSaveSettings => 'सेटिङहरू बचत गर्नुहोस्';

  @override
  String get smsSendSectionTitle => 'अहिले सारांश पठाउनुहोस्';

  @override
  String get smsSendRecipientPrefix => 'तलको सन्देश पठाउँदै छ:';

  @override
  String get smsSendNoPhone => 'पहिले माथि फोन नम्बर थप्नुहोस् र बचत गर्नुहोस्।';

  @override
  String get smsSendButton => 'अहिले सारांश पठाउनुहोस्';

  @override
  String get smsErrorEnterPhone => 'कृपया फोन नम्बर प्रविष्ट गर्नुहोस्';

  @override
  String get smsErrorInvalidPhone => 'अन्तर्राष्ट्रिय ढाँचामा मान्य फोन नम्बर प्रविष्ट गर्नुहोस्, जस्तै +919876543210';

  @override
  String get smsSuccessSaved => 'SMS सेटिङहरू सफलतापूर्वक बचत गरियो!';

  @override
  String get smsErrorAddPhoneFirst => 'पहिले फोन नम्बर थप्नुहोस् र बचत गर्नुहोस्';

  @override
  String get smsSuccessSent => 'तपाईंको फोनमा सारांश पठाइयो!';

  @override
  String get smsErrorRateLimit => 'तपाईं प्रति मिनेट एक सारांश पठाउन सक्नुहुन्छ, कृपया केहि बेर पर्खनुहोस् र फेरि प्रयास गर्नुहोस्।';

  @override
  String get smsErrorSessionExpired => 'तपाईंको सत्र समाप्त भएको छ। कृपया फेरि लग इन गर्नुहोस्।';

  @override
  String get smsErrorNetwork => 'सर्भरसँग जडान गर्न सकिएन। आफ्नो जडान जाँच गर्नुहोस् र फेरि प्रयास गर्नुहोस्।';

  @override
  String get smsErrorGeneric => 'केहि गलत भयो। कृपया फेरि प्रयास गर्नुहोस्।';

  @override
  String get smsLoadError => 'तपाईंको SMS सेटिङहरू लोड गर्न सकिएन। रिफ्रेस गर्न तान्नुहोस् वा फेरि प्रयास गर्नुहोस्।';

  @override
  String get smsSummaryMessage => '🌸 Rhythma स्वास्थ्य सारांश\nयो Rhythma बाट तपाईंको अन-डिमांड सारांश हो।\nतपाईंको पछिल्लो साइकल इनसाइटहरूको लागि एप खोल्नुहोस्।\nअनसब्सक्राइब गर्न STOP जवाफ दिनुहोस्।';

  @override
  String insightsLoadError(String error) {
    return 'तपाईंको इनसाइटहरू लोड गर्न सकिएन: \$\\1';
  }

  @override
  String get insightsNotEnoughData => 'तपाईंको पूर्ण स्वास्थ्य इनसाइटहरू अनलक गर्न साइकल ट्याबमा केही थप साइकलहरू लग गर्नुहोस्।';

  @override
  String get insightsNoSymptomsYet => 'अहिलेसम्म कुनै लक्षण लग गरिएको छैन — यहाँ ढाँचाहरू हेर्न साइकल ट्याबमा केही लग गर्नुहोस्।';

  @override
  String get insightsNotEnoughTrendData => 'यहाँ तपाईंको प्रवृत्ति हेर्न कम्तिमा दुई साइकलहरू लग गर्नुहोस्।';

  @override
  String get assistantAccessibilitySuggestedPrompt => 'सुझाइएको प्रम्प्ट';

  @override
  String get assistantAccessibilityMessageInput => 'सन्देश इनपुट';

  @override
  String get assistantAccessibilityMessageInputHint => 'आफ्नो प्रश्न यहाँ टाइप गर्नुहोस्';

  @override
  String get assistantAccessibilitySendMessage => 'सन्देश पठाउनुहोस्';

  @override
  String get assistantAccessibilitySendMessageHint => 'तपाईंको सन्देश सहायकलाई पठाउँछ';

  @override
  String get assistantAccessibilityTyping => 'सहायक टाइप गर्दैछ';

  @override
  String get languageSelectionError => 'भाषा बचत गर्न सकिएन। कृपया फेरि प्रयास गर्नुहोस्।';

  @override
  String get deleteAccount => 'खाता मेटाउनुहोस्';

  @override
  String get deleteAccountConfirmationTitle => 'खाता मेटाउने?';

  @override
  String get deleteAccountConfirmationDesc => 'यो कार्य स्थायी हो र पूर्ववत गर्न सकिँदैन। तपाईंको सबै डाटा मेटाइनेछ।';

  @override
  String get accountDeletedSuccess => 'खाता सफलतापूर्वक मेटाइयो।';

  @override
  String get langGujarati => 'ગુજરાતી (Gujarati)';

  @override
  String get welcomeToRhythma => 'Welcome to Rhythma';

  @override
  String get loginOrSignUpWithPhone => 'Log in or sign up with your phone number.';

  @override
  String get enterOtpSentToPhone => 'Enter the OTP sent to your phone';

  @override
  String get phoneNumber => 'Phone Number';

  @override
  String get getOtp => 'Get OTP';

  @override
  String get sendingOtp => 'Sending OTP...';

  @override
  String get otp => 'OTP';

  @override
  String get verifyOtp => 'Verify OTP';

  @override
  String get verifying => 'Verifying...';

  @override
  String get useDifferentPhoneNumber => 'Use a different phone number';

  @override
  String get pleaseEnterPhoneNumber => 'Please enter your phone number.';

  @override
  String get pleaseEnterValidPhoneNumber => 'Please enter a valid phone number with country code (e.g., +91).';

  @override
  String get verificationFailed => 'Verification failed';

  @override
  String otpSentTo(String phone) => 'OTP sent to $phone';

  @override
  String get pleaseEnterOtp => 'Please enter the OTP.';

  @override
  String get invalidOtp => 'Invalid OTP. Please try again.';

  @override
  String get failedToGetIdToken => 'Failed to get ID token';
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
