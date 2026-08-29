// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Marathi (`mr`).
class AppLocalizationsMr extends AppLocalizations {
  AppLocalizationsMr([String locale = 'mr']) : super(locale);

  @override
  String get appTitle => 'रिद्मा';

  @override
  String get settingsTitle => 'सेटिंग्ज';

  @override
  String get appPreferences => 'अॅप प्राधान्ये';

  @override
  String get languagePreferences => 'भाषा प्राधान्ये';

  @override
  String get darkMode => 'डार्क मोड';

  @override
  String get themeToggle => 'थीम बदला';

  @override
  String get notificationsTitle => 'सूचना';

  @override
  String get cycleTrackingReminders => 'मासिक पाळी ट्रॅकिंग सूचना';

  @override
  String get medicineAlerts => 'औषध अलर्ट';

  @override
  String get wellnessTips => 'आरोग्य टिप्स';

  @override
  String get securityPrivacyTitle => 'सुरक्षा आणि गोपनीयता';

  @override
  String get appPermissions => 'अॅप परवानग्या';

  @override
  String get privacyPolicy => 'गोपनीयता धोरण';

  @override
  String get logOut => 'लॉग आउट';

  @override
  String get logoutConfirmation =>
      'तुम्हाला रिद्मामधून नक्की लॉग आउट करायचे आहे का?';

  @override
  String get cancel => 'रद्द करा';

  @override
  String get loggedOutSuccess => 'यशस्वीरित्या लॉग आउट झाले';

  @override
  String get selectLanguage => 'भाषा निवडा';

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
  String get homeGreeting => 'नमस्कार';

  @override
  String get homePhaseDesc => 'दिवस 14 · ओव्हुलेशन टप्पा';

  @override
  String get homeNextPeriod => 'पुढील पाळी';

  @override
  String get homeDaysLabel => 'दिवस';

  @override
  String get homeFertileWindow => 'सुपीक काळ · ';

  @override
  String get homeHighEnergy => 'उच्च ऊर्जा';

  @override
  String get homeFertileWindowDisclaimer =>
      'हा तुमच्या नोंदवलेल्या माहितीवर आधारित अंदाज आहे, वैद्यकीय किंवा गर्भनिरोधक सल्ला नाही.';

  @override
  String get homeAiTitle => 'रिद्मा एआय';

  @override
  String get homeAiSubtitle =>
      'मला तुमच्या शरीराबद्दल काहीही विचारा,\nतुमच्या भाषेत.';

  @override
  String get homeAiPrompt => 'माझी पाळी अनियमित का आहे?';

  @override
  String get homeFeelingTitle => 'आज तुम्हाला कसे वाटत आहे?';

  @override
  String get homeLogAll => 'सर्व नोंदवा';

  @override
  String get homeLogFlow => 'प्रवाह';

  @override
  String get homeLogMood => 'मनःस्थिती';

  @override
  String get homeLogSleep => 'झोप';

  @override
  String get homeLogStress => 'तणाव';

  @override
  String get homeWeeklyInsightLabel => 'साप्ताहिक अंतर्दृष्टी';

  @override
  String get homeWeeklyInsightTitle =>
      'या आठवड्यात तुमची झोप 12% सुधारली - तुमचे चक्र तुम्हाला धन्यवाद देईल.';

  @override
  String get homeWeeklyInsightDesc =>
      'ओव्हुलेशनपूर्वी सातत्यपूर्ण विश्रांती हार्मोनल संतुलनास समर्थन देते.';

  @override
  String get homeLearnTitle => 'रिद्मासोबत शिका';

  @override
  String get homeLearnPcos => 'PCOS समजून घेणे';

  @override
  String get homeLearnHormones => 'हार्मोन्स 101';

  @override
  String get homeLearnIron => 'लोहयुक्त पदार्थ';

  @override
  String get homeArticle => 'लेख';

  @override
  String get homeFailedLoad => 'Failed to load dashboard';

  @override
  String get homeRetry => 'Retry';

  @override
  String homeSavedDataNotice(String when) {
    return '$when चा जतन केलेला डेटा दाखवत आहे';
  }

  @override
  String get homeCouldNotRefresh => 'रिफ्रेश करता आले नाही — तुम्ही कदाचित ऑफलाइन आहात';

  @override
  String get homeSavedDataTooOld => 'तुमचा जतन केलेला डेटा इतका जुना आहे की विश्वासार्ह चक्र दिवस दाखवता येत नाही. रिफ्रेश करण्यासाठी इंटरनेटशी जोडा.';

  @override
  String get homeAgeJustNow => 'आत्ताच';

  @override
  String homeAgeMinutes(String count) {
    return '$count मिनिटांपूर्वी';
  }

  @override
  String homeAgeHours(String count) {
    return '$count तासांपूर्वी';
  }

  @override
  String homeAgeDays(String count) {
    return '$count दिवसांपूर्वी';
  }

  @override
  String get homeMhs => 'MHS';

  @override
  String get homeCvi => 'CVI';

  @override
  String get homeSleep => 'झोप';

  @override
  String get homeComingSoon => 'Coming Soon';

  @override
  String homeUnderDevelopment(String topic) {
    return '$topic is currently under development.';
  }

  @override
  String get homeErrorNetwork =>
      'कृपया तुमचे इंटरनेट कनेक्शन तपासा आणि पुन्हा प्रयत्न करा.';

  @override
  String get homeErrorAuth =>
      'तुमचे सत्र कालबाह्य झाले आहे. कृपया पुन्हा लॉग इन करा.';

  @override
  String get homeErrorServer =>
      'आमच्या बाजूला काहीतरी चूक झाली आहे. कृपया नंतर पुन्हा प्रयत्न करा.';

  @override
  String get homeErrorGeneric =>
      'डेटा लोड करण्यात असमर्थ. कृपया पुन्हा प्रयत्न करा.';

  @override
  String homeQuickLogTitle(String label) {
    return '$label नोंदवा';
  }

  @override
  String homeQuickLogSaved(String label, String value) {
    return '$label नोंदवले गेले: $value';
  }

  @override
  String get homePrivacySecurity => 'Privacy & Security';

  @override
  String get homeOk => 'OK';

  @override
  String get cycleTrackerTitle => 'चक्र ट्रॅकर';

  @override
  String get cycleToday => 'आज';

  @override
  String get cyclePhasePeriod => 'मासिक पाळी';

  @override
  String get cyclePhaseFollicular => 'फॉलिक्युलर';

  @override
  String get cyclePhaseOvulation => 'ओव्हुलेशन';

  @override
  String get cyclePhaseLuteal => 'ल्युटियल';

  @override
  String get logFor => 'साठी नोंदवा';

  @override
  String get logNone => 'काहीही नाही';

  @override
  String get logLight => 'हलका';

  @override
  String get logMedium => 'मध्यम';

  @override
  String get logHeavy => 'जास्त';

  @override
  String get logEnergyLow => 'कमी';

  @override
  String get logEnergyMid => 'मध्यम';

  @override
  String get logEnergyHigh => 'उच्च';

  @override
  String get logSleep1 => '<5 तास';

  @override
  String get logSleep2 => '5-7 तास';

  @override
  String get logSleep3 => '7-9 तास';

  @override
  String get logSleep4 => '9+ तास';

  @override
  String get logSympCramps => 'पेटके';

  @override
  String get logSympHeadache => 'डोकेदुखी';

  @override
  String get logSympBloating => 'फुगणे';

  @override
  String get logSympAcne => 'मुरुमे';

  @override
  String get logLabelEnergy => 'ऊर्जा';

  @override
  String get logLabelSymptoms => 'लक्षणे';

  @override
  String get logToday => 'Log Today';

  @override
  String get logTitle => 'Log your day';

  @override
  String get logFlowIntensity => 'Flow Intensity';

  @override
  String get logMood => 'Mood';

  @override
  String get logSleepHours => 'Sleep Hours';

  @override
  String get logStressLevel => 'Stress Level';

  @override
  String get logSave => 'Save Log';

  @override
  String get logSympFatigue => 'Fatigue';

  @override
  String get logSympNausea => 'Nausea';

  @override
  String get logSympBackPain => 'Back Pain';

  @override
  String get assistantTitle => 'रिद्मा सहाय्यक';

  @override
  String get assistantSubtitle => 'तुमचा वैयक्तिक आरोग्य सोबती';

  @override
  String get assistantInputHint => 'तुमचा प्रश्न विचारा...';

  @override
  String assistantWelcome(String name) {
    return 'नमस्कार आर्या 🌸 मी रिद्मा आहे, तुमची वैयक्तिक आरोग्य सोबती. मला तुमच्या चक्राबद्दल, लक्षणांबद्दल काहीही विचारा — इंग्रजी, हिंदी, मराठी किंवा तमिळमध्ये.';
  }

  @override
  String get assistantSug1 => 'माझी पाळी अनियमित का आहे?';

  @override
  String get assistantSug2 => 'तीव्र वेदना कशामुळे होतात?';

  @override
  String get assistantSug3 => '35 दिवसांचे चक्र सामान्य आहे का?';

  @override
  String get assistantSug4 => 'पीएमएसमध्ये उपयुक्त आहार';

  @override
  String get assistantSug5 => 'माझे पीरियड्स अनियमित आहेत — हे सामान्य आहे का?';

  @override
  String get assistantDisclaimer =>
      'हा सहाय्यक फक्त सामान्य आरोग्य माहिती देतो आणि तो व्यावसायिक वैद्यकीय सल्ल्याचा पर्याय नाही.';

  @override
  String get insightsTitle => 'आरोग्य अंतर्दृष्टी';

  @override
  String get insightsSubtitle => 'मागील 90 दिवस';

  @override
  String get insightsMhsLabel => 'मासिक पाळी आरोग्य स्कोअर';

  @override
  String get insightsMhsDelta => 'मागील चक्राच्या तुलनेत +6';

  @override
  String get insightsVar => 'चक्र परिवर्तनशीलता';

  @override
  String get insightsAvgCycle => 'सरासरी चक्र';

  @override
  String get insightsRegular => 'नियमित';

  @override
  String get insightsModerate => 'मध्यम';

  @override
  String get insightsTrendLabel => 'चक्र लांबीचा कल';

  @override
  String get insightsStabilizing => 'स्थिर होत आहे';

  @override
  String get insightsHealthy => 'निरोगी';

  @override
  String get insightsSymptomsLabel => 'लक्षणे नमुने';

  @override
  String get insightsMoodSwings => 'मूड बदलणे';

  @override
  String get insightsWellnessLabel => 'आरोग्य शिफारसी';

  @override
  String get insightsRec1 => 'पाळी सुरू होण्यापूर्वी लोहयुक्त पदार्थ घ्या';

  @override
  String get insightsRec2 => 'ल्युटियल टप्प्यात 10 मिनिटे योग करा';

  @override
  String get insightsRec3 => 'ओव्हुलेशनच्या आठवड्यात 2.5L पाणी प्या';

  @override
  String get insightsDisclaimer =>
      'ही माहिती तुम्ही नोंदवलेल्या डेटावर आधारित आहे आणि केवळ वैयक्तिक ट्रॅकिंगसाठी आहे. हे वैद्यकीय निदान नाही आणि पात्र आरोग्य तज्ञाच्या सल्ल्याचा पर्याय नाही.';

  @override
  String get profileTitle => 'प्रोफाइल';

  @override
  String get profileYearsOld => 'वर्षांची';

  @override
  String get profileCycleDay => 'चक्राचा दिवस';

  @override
  String get profileQuickStats => 'त्वरित आकडेवारी';

  @override
  String get profileAvgCycleLength => 'सरासरी चक्राची लांबी';

  @override
  String get profileAvgMentalHealth => 'सरासरी मानसिक आरोग्य';

  @override
  String get profileCycleVariability => 'चक्र परिवर्तनशीलता';

  @override
  String get profileLastCycleLength => 'शेवटच्या चक्राची लांबी';

  @override
  String get profileAccountSettings => 'खाते सेटिंग्ज';

  @override
  String get profileEditInfo => 'प्रोफाइल माहिती संपादित करा';

  @override
  String get profileEmergencyContact => 'वैद्यकीय आणीबाणी संपर्क';

  @override
  String get profileAppSettings => 'अॅप सेटिंग्ज';

  @override
  String get profileEditProfile => 'प्रोफाइल संपादित करा';

  @override
  String get profileName => 'नाव';

  @override
  String get profileAge => 'वय';

  @override
  String get profileAvgCycleDays => 'सरासरी चक्राची लांबी (दिवस)';

  @override
  String get profileSaveChanges => 'बदल जतन करा';

  @override
  String get profileNameEmptyError => 'Please enter a valid name';

  @override
  String get profileAddContact => 'संपर्क जोडा';

  @override
  String get profileEditContact => 'संपर्क संपादित करा';

  @override
  String get profilePhone => 'फोन';

  @override
  String get profileSave => 'जतन करा';

  @override
  String get profileEmergencyContactsTitle => 'आणीबाणी संपर्क';

  @override
  String get profileAddNew => 'नवीन जोडा';

  @override
  String get profileNoContacts =>
      'अद्याप कोणताही आणीबाणी संपर्क सेट केलेला नाही.';

  @override
  String get profileAgeInvalidError => 'कृपया वैध वय प्रविष्ट करा';

  @override
  String get profileCycleInvalidError =>
      'कृपया वैध मासिक पाळी चक्र कालावधी प्रविष्ट करा';

  @override
  String get profilePhoneInvalidError => 'कृपया वैध फोन क्रमांक प्रविष्ट करा';

  @override
  String get contactNameRequiredError => 'Contact name is required';

  @override
  String get edit => 'संपादित करा';

  @override
  String get delete => 'हटवा';

  @override
  String get onboardingAvatarOption => 'अवतार पर्याय';

  @override
  String get navHome => 'होम';

  @override
  String get navCycle => 'सायकल';

  @override
  String get navAsk => 'विचारा';

  @override
  String get navInsights => 'अंतर्ज्ञान';

  @override
  String get navYou => 'प्रोफाइल';

  @override
  String get settingsHelpSupport => 'मदत आणि समर्थन';

  @override
  String get settingsContactUs => 'आमच्याशी संपर्क साधा / बगची तक्रार करा';

  @override
  String get settingsContactDesc => 'आमच्या सपोर्ट टीमला ईमेल पाठवा';

  @override
  String get settingsEmailError =>
      'ईमेल ॲप उघडू शकलो नाही. कृपया आम्हाला support@rhythma.com वर ईमेल करा';

  @override
  String get settingsData => 'Data';

  @override
  String get settingsExportData => 'Export My Data';

  @override
  String get settingsExportDataDesc =>
      'Download your profile, contacts, and cycle logs as JSON';

  @override
  String get settingsExportSuccess => 'Data exported successfully';

  @override
  String get onboardingPrivacyNote =>
      'तुमची माहिती तुमच्या डिव्हाइसवर राहते. तुमच्या परवानगीशिवाय आम्ही कधीही तुमचा डेटा शेअर करत नाही.';

  @override
  String get onboardingNext => 'पुढे';

  @override
  String get onboardingBack => 'मागे';

  @override
  String get onboardingSkip => 'वगळा';

  @override
  String get onboardingDone => 'सुरू करा';

  @override
  String get onboardingStep1Title => 'तुमची भाषा निवडा';

  @override
  String get onboardingStep1Subtitle =>
      'तुम्हाला सर्वात सोयीस्कर वाटणारी भाषा निवडा';

  @override
  String get onboardingStep2Title => 'स्वतःबद्दल सांगा';

  @override
  String get onboardingStep2Subtitle =>
      'यामुळे आम्हाला तुमचा अनुभव वैयक्तिक बनवण्यास मदत होते';

  @override
  String get onboardingNameHint => 'तुमचे नाव किंवा टोपणनाव';

  @override
  String get onboardingNameLabel => 'नाव';

  @override
  String get onboardingAgeLabel => 'वय';

  @override
  String get onboardingHeightLabel => 'उंची (सेमी)';

  @override
  String get onboardingWeightLabel => 'वजन (किग्रा)';

  @override
  String get onboardingAvatarLabel => 'अवतार निवडा';

  @override
  String get onboardingStep3Title => 'तुमचे चक्र';

  @override
  String get onboardingStep3Subtitle =>
      'तुमच्या चक्राबद्दल सांगा — माहीत नसल्यास वगळू शकता';

  @override
  String get onboardingLastPeriodLabel => 'शेवटच्या मासिक पाळीची सुरुवात';

  @override
  String get onboardingCycleLengthLabel => 'सरासरी चक्र कालावधी (दिवस)';

  @override
  String get onboardingPeriodDurationLabel =>
      'सरासरी मासिक पाळी कालावधी (दिवस)';

  @override
  String get onboardingCycleRegularityLabel => 'चक्र नियमितता';

  @override
  String get onboardingRegular => 'नियमित';

  @override
  String get onboardingIrregular => 'अनियमित';

  @override
  String get onboardingStep4Title => 'थोडे अधिक (वैकल्पिक)';

  @override
  String get onboardingStep4Subtitle => 'प्रादेशिक आरोग्य टिप्ससाठी';

  @override
  String get onboardingPhoneLabel => 'फोन नंबर (वैकल्पिक)';

  @override
  String get onboardingPhoneHint => 'e.g. +919876543210';

  @override
  String get onboardingCityLabel => 'शहर (वैकल्पिक)';

  @override
  String get onboardingStateLabel => 'राज्य / पिन कोड (वैकल्पिक)';

  @override
  String get onboardingStep5Title => 'अपडेट राहा';

  @override
  String get onboardingStep5Subtitle =>
      'सूचना सक्षम करा जेणेकरून Rhythma योग्य वेळी आठवण करून देईल';

  @override
  String get onboardingEnableNotifications => 'चक्र स्मरणपत्रे सक्षम करा';

  @override
  String get onboardingNotificationsDesc =>
      'मासिक पाळी आणि ओव्हुलेशनपूर्वी सौम्य स्मरणपत्रे मिळवा';

  @override
  String get onboardingDataConsentLabel =>
      'मी या डिव्हाइसवर माझा आरोग्य डेटा स्थानिकपणे संग्रहित करण्यास संमती देते';

  @override
  String get onboardingDataConsentRequired => 'सुरू ठेवण्यासाठी स्वीकारा';

  @override
  String get onboardingNameRequired => 'कृपया तुमचे नाव प्रविष्ट करा';

  @override
  String get onboardingAgeInvalid => 'कृपया वैध वय प्रविष्ट करा (10–120)';

  @override
  String get onboardingHeightInvalid =>
      'कृपया वैध उंची प्रविष्ट करा (50–250 सेमी)';

  @override
  String get onboardingWeightInvalid =>
      'कृपया वैध वजन प्रविष्ट करा (20–300 किग्रा)';

  @override
  String get onboardingPhoneInvalid => 'कृपया वैध फोन नंबर प्रविष्ट करा';

  @override
  String get onboardingAgeRequired =>
      'कृपया तुमचे वय प्रविष्ट करा किंवा एक श्रेणी निवडा';

  @override
  String get onboardingHeightRequired =>
      'कृपया तुमची उंची प्रविष्ट करा किंवा एक श्रेणी निवडा';

  @override
  String get onboardingWeightRequired =>
      'कृपया तुमचे वजन प्रविष्ट करा किंवा एक श्रेणी निवडा';

  @override
  String get onboardingNotSure => 'पक्का नाही';

  @override
  String get onboardingApproximate => 'अंदाजे';

  @override
  String get onboardingAgeHint => 'तुमचे वय प्रविष्ट करा';

  @override
  String get onboardingAgeUnit => 'वर्षे';

  @override
  String get onboardingHeightHint => 'तुमची उंची प्रविष्ट करा';

  @override
  String get onboardingHeightUnit => 'सेमी';

  @override
  String get onboardingWeightHint => 'तुमचे वजन प्रविष्ट करा';

  @override
  String get onboardingWeightUnit => 'किलो';

  @override
  String get onboardingRangeUnder18 => '18 पेक्षा कमी';

  @override
  String get onboardingRange18to25 => '18–25';

  @override
  String get onboardingRange26to35 => '26–35';

  @override
  String get onboardingRange36to50 => '36–50';

  @override
  String get onboardingRange51to65 => '51–65';

  @override
  String get onboardingRangeOver65 => '65 पेक्षा जास्त';

  @override
  String get onboardingRangeUnder150 => '150 सेमी पेक्षा कमी';

  @override
  String get onboardingRange150to160 => '150–160 सेमी';

  @override
  String get onboardingRange161to170 => '161–170 सेमी';

  @override
  String get onboardingRange171to180 => '171–180 सेमी';

  @override
  String get onboardingRangeOver180 => '180 सेमी पेक्षा जास्त';

  @override
  String get onboardingRangeUnder50kg => '50 किलो पेक्षा कमी';

  @override
  String get onboardingRange50to65kg => '50–65 किलो';

  @override
  String get onboardingRange66to80kg => '66–80 किलो';

  @override
  String get onboardingRange81to100kg => '81–100 किलो';

  @override
  String get onboardingRangeOver100kg => '100 किलो पेक्षा जास्त';

  @override
  String get onboardingTapToSelectDate => 'तारीख निवडण्यासाठी टॅप करा';

  @override
  String get onboardingDays => 'दिवस';

  @override
  String get onboardingApproximateLabel => 'When was your last period?';

  @override
  String get onboardingApproximateLessWeek => 'Less than a week ago';

  @override
  String get onboardingApproximate1to2Weeks => '1–2 आठड्यांपूर्वी';

  @override
  String get onboardingApproximate3to4Weeks => '3–4 आठड्यांपूर्वी';

  @override
  String get onboardingApproximateMoreMonth => 'एका महिन्यापेक्षा जास्त पूर्वी';

  @override
  String get onboardingPickExactDate => 'त्याऐवजी अचूक तारीख निवडा';

  @override
  String get onboardingLastPeriodRequired =>
      'कृपया आपल्या शेवटच्या मासिक पळीची सुरुवात कधी झाली ते निवडा';

  @override
  String get nudgeCompleteProfileTitle => 'अधिक अचूक अंदाज हवे आहेत?';

  @override
  String get nudgeCompleteProfileBody =>
      'चक्र अंदाज सुधारण्यासाठी आपल्या शेवटच्या मासिक पळीची अचूक सुरुवातीची तारीख जोडा.';

  @override
  String get nudgeCompleteProfileAction => 'अद्ययावत करा';

  @override
  String get nudgeCompleteProfileDismiss => 'नंतर';

  @override
  String get smsScreenTitle => 'एसएमएस सारांश';

  @override
  String get smsScreenSubtitle => 'अ‍ॅपशिवायही माहिती मिळवा';

  @override
  String get smsInfoCardTitle => 'साप्ताहिक आरोग्य सारांश';

  @override
  String get smsInfoCardBody =>
      'दर आठवड्याला, रिद्मा तुम्हाला तुमच्या चक्राची स्थिती, आरोग्य गुण आणि महत्त्वाच्या नमुन्यांचा थोडक्यात सारांश थेट एसएमएसद्वारे तुमच्या फोनवर पाठवेल, डेटा किंवा अ‍ॅपशिवायही चालते.';

  @override
  String get smsConfigTitle => 'कॉन्फिगरेशन';

  @override
  String get smsPhoneLabel => 'फोन नंबर';

  @override
  String get smsPhoneHint => '+91 98765 43210';

  @override
  String get smsEnableWeekly => 'साप्ताहिक एसएमएस सक्षम करा';

  @override
  String get smsSaveSettings => 'सेटिंग्ज जतन करा';

  @override
  String get smsSendSectionTitle => 'आत्ता सारांश पाठवा';

  @override
  String get smsSendRecipientPrefix => 'खालील संदेश या नंबरवर पाठवला जाईल:';

  @override
  String get smsSendNoPhone => 'आधी वर फोन नंबर जोडा आणि जतन करा.';

  @override
  String get smsSendButton => 'सारांश आत्ता पाठवा';

  @override
  String get smsErrorEnterPhone => 'कृपया फोन नंबर टाका';

  @override
  String get smsErrorInvalidPhone =>
      'आंतरराष्ट्रीय स्वरूपात वैध फोन नंबर टाका, उदा. +919876543210';

  @override
  String get smsSuccessSaved => 'एसएमएस सेटिंग्ज यशस्वीरित्या जतन झाल्या!';

  @override
  String get smsErrorAddPhoneFirst => 'आधी फोन नंबर जोडा आणि जतन करा';

  @override
  String get smsSuccessSent => 'सारांश तुमच्या फोनवर पाठवला गेला!';

  @override
  String get smsErrorRateLimit =>
      'तुम्ही दर मिनिटाला फक्त एक सारांश पाठवू शकता, कृपया थोड्या वेळाने पुन्हा प्रयत्न करा.';

  @override
  String get smsErrorSessionExpired =>
      'तुमचे सत्र संपले आहे. कृपया पुन्हा लॉग इन करा.';

  @override
  String get smsErrorNetwork =>
      'सर्व्हरपर्यंत पोहोचू शकलो नाही. तुमचे कनेक्शन तपासा आणि पुन्हा प्रयत्न करा.';

  @override
  String get smsErrorGeneric => 'काहीतरी चुकले. कृपया पुन्हा प्रयत्न करा.';

  @override
  String get smsLoadError =>
      'तुमच्या एसएमएस सेटिंग्ज लोड होऊ शकल्या नाहीत. रिफ्रेश करा किंवा पुन्हा प्रयत्न करा.';

  @override
  String get smsSummaryMessage =>
      '🌸 रिद्मा आरोग्य सारांश\nहा रिद्माकडून तुमचा ऑन-डिमांड सारांश आहे.\nतुमच्या नवीनतम चक्र माहितीसाठी अ‍ॅप उघडा.\nसदस्यता रद्द करण्यासाठी STOP उत्तर द्या.';

  @override
  String insightsLoadError(String error) {
    return 'तुमची अंतर्दृष्टी लोड करता आली नाही: $error';
  }

  @override
  String get insightsNotEnoughData =>
      'तुमचे संपूर्ण आरोग्य अंतर्दृष्टी अनलॉक करण्यासाठी Cycle टॅबवर आणखी काही चक्र लॉग करा.';

  @override
  String get insightsNoSymptomsYet =>
      'अद्याप कोणतीही लक्षणे लॉग केलेली नाहीत - Cycle टॅबवर काही लॉग करा.';

  @override
  String get insightsNotEnoughTrendData =>
      'तुमचा ट्रेंड पाहण्यासाठी किमान दोन चक्र लॉग करा.';

  @override
  String get assistantAccessibilitySuggestedPrompt => 'Suggested prompt';

  @override
  String get assistantAccessibilityMessageInput => 'Message input';

  @override
  String get assistantAccessibilityMessageInputHint =>
      'Type your question here';

  @override
  String get assistantAccessibilitySendMessage => 'Send message';

  @override
  String get assistantAccessibilitySendMessageHint =>
      'Sends your message to the assistant';

  @override
  String get assistantAccessibilityTyping => 'Assistant is typing';

  @override
  String get languageSelectionError =>
      'भाषा जतन करण्यात असमर्थ. कृपया पुन्हा प्रयत्न करा.';

  @override
  String get deleteAccount => 'Delete Account';

  @override
  String get deleteAccountConfirmationTitle => 'Delete Account?';

  @override
  String get deleteAccountConfirmationDesc =>
      'This action is permanent and cannot be undone. All your data will be wiped.';

  @override
  String get accountDeletedSuccess => 'Account deleted successfully.';

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
  String get ayurvedaWellnessTitle => 'आयुर्वेद-प्रेरित आरोग्य माहिती';

  @override
  String get ayurvedaDisclaimer => 'ही माहिती केवळ शैक्षणिक उद्देशांसाठी आहे. आयुर्वेद-प्रेरित मजकूर वैद्यकीय सल्ला, निदान किंवा उपचारांचा पर्याय नाही.';

  @override
  String get ayurvedaMenstrualTitle => 'विश्रांती आणि आत्मचिंतन';

  @override
  String get ayurvedaMenstrualDescription => 'आयुर्वेदिक परंपरेनुसार मासिक पाळीदरम्यान विश्रांती, आत्मचिंतन आणि सौम्य स्व-देखभालीवर भर दिला जातो.';

  @override
  String get ayurvedaFollicularTitle => 'नवचैतन्य आणि सक्रियता';

  @override
  String get ayurvedaFollicularDescription => 'आयुर्वेदिक आरोग्य परंपरांमध्ये मासिक पाळीनंतरचा काळ नवचैतन्य आणि हळूहळू वाढणाऱ्या सक्रियतेशी जोडला जातो.';

  @override
  String get ayurvedaOvulationTitle => 'संतुलन आणि सुसंवाद';

  @override
  String get ayurvedaOvulationDescription => 'काही आयुर्वेदिक परंपरांनुसार चक्राच्या मध्यावधीला ऊर्जा, चैतन्य आणि सामाजिक सुसंवादाचा काळ मानला जातो.';

  @override
  String get ayurvedaLutealTitle => 'स्थैर्य आणि दिनचर्या';

  @override
  String get ayurvedaLutealDescription => 'आयुर्वेदिक आरोग्य परंपरांमध्ये चक्राच्या उत्तरार्धात शांत दिनचर्या आणि सजग स्व-देखभालीवर भर दिला जातो.';
}
