// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Hindi (`hi`).
class AppLocalizationsHi extends AppLocalizations {
  AppLocalizationsHi([String locale = 'hi']) : super(locale);

  @override
  String get appTitle => 'Rhythma';

  @override
  String get settingsTitle => 'सेटिंग्स';

  @override
  String get appPreferences => 'ऐप प्राथमिकताएं';

  @override
  String get languagePreferences => 'भाषा प्राथमिकताएं';

  @override
  String get darkMode => 'डार्क मोड';

  @override
  String get themeToggle => 'थीम टॉगल';

  @override
  String get notificationsTitle => 'सूचनाएं';

  @override
  String get cycleTrackingReminders => 'मासिक धर्म चक्र अनुस्मारक';

  @override
  String get medicineAlerts => 'दवा अलर्ट';

  @override
  String get wellnessTips => 'स्वास्थ्य संबंधी सुझाव';

  @override
  String get securityPrivacyTitle => 'सुरक्षा और गोपनीयता';

  @override
  String get appPermissions => 'ऐप अनुमतियां';

  @override
  String get privacyPolicy => 'गोपनीयता नीति';

  @override
  String get logOut => 'लॉग आउट';

  @override
  String get logoutConfirmation =>
      'क्या आप वाकई Rhythma से लॉग आउट करना चाहते हैं?';

  @override
  String get cancel => 'रद्द करें';

  @override
  String get loggedOutSuccess => 'सफलतापूर्वक लॉग आउट हो गया';

  @override
  String get selectLanguage => 'भाषा चुनें';

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
  String get homePhaseDesc => 'दिन 14 · ओव्यूलेशन चरण';

  @override
  String get homeNextPeriod => 'अगला मासिक धर्म';

  @override
  String get homeDaysLabel => 'दिन';

  @override
  String get homeFertileWindow => 'उपजाऊ अवधि · ';

  @override
  String get homeHighEnergy => 'उच्च ऊर्जा';

  @override
  String get homeFertileWindowDisclaimer =>
      'यह आपके लॉग किए गए डेटा पर आधारित एक अनुमान है, चिकित्सीय या गर्भनिरोधक सलाह नहीं।';

  @override
  String get homeAiTitle => 'रिद्मा एआई';

  @override
  String get homeAiSubtitle =>
      'अपने शरीर से जुड़ा कोई भी प्रश्न अपनी भाषा में मुझसे पूछें।';

  @override
  String get homeAiPrompt => 'मेरे मासिक धर्म अनियमित क्यों हैं?';

  @override
  String get homeFeelingTitle => 'आज आप कैसा महसूस कर रही हैं?';

  @override
  String get homeLogAll => 'सभी लॉग करें';

  @override
  String get homeLogFlow => 'प्रवाह';

  @override
  String get homeLogMood => 'मनोदशा';

  @override
  String get homeLogSleep => 'नींद';

  @override
  String get homeLogStress => 'तनाव';

  @override
  String get homeWeeklyInsightLabel => 'साप्ताहिक अंतर्दृष्टि';

  @override
  String get homeWeeklyInsightTitle =>
      'इस सप्ताह आपकी नींद में 12% सुधार हुआ है। यह आपके मासिक धर्म चक्र के लिए लाभदायक हो सकता है।';

  @override
  String get homeWeeklyInsightDesc =>
      'ओव्यूलेशन से पहले लगातार आराम हार्मोनल संतुलन का समर्थन करता है।';

  @override
  String get homeLearnTitle => 'रिद्मा के साथ सीखें';

  @override
  String get homeLearnPcos => 'PCOS को समझना';

  @override
  String get homeLearnHormones => 'हार्मोन 101';

  @override
  String get homeLearnIron => 'आयरन से भरपूर खाद्य पदार्थ';

  @override
  String get homeArticle => 'लेख';

  @override
  String get homeFailedLoad => 'Failed to load dashboard';

  @override
  String get homeRetry => 'Retry';

  @override
  String get homeMhs => 'MHS';

  @override
  String get homeCvi => 'CVI';

  @override
  String get homeSleep => 'Sleep';

  @override
  String get homeComingSoon => 'Coming Soon';

  @override
  String homeUnderDevelopment(String topic) {
    return '$topic is currently under development.';
  }

  @override
  String get homeErrorNetwork =>
      'Please check your internet connection and try again.';

  @override
  String get homeErrorAuth => 'Your session has expired. Please log in again.';

  @override
  String get homeErrorServer =>
      'Something went wrong on our end. Please try again later.';

  @override
  String get homeErrorGeneric => 'Unable to load data. Please try again.';

  @override
  String homeQuickLogTitle(String label) {
    return 'Log $label';
  }

  @override
  String homeQuickLogSaved(String label, String value) {
    return '$label logged: $value';
  }

  @override
  String get homePrivacySecurity => 'Privacy & Security';

  @override
  String get homeOk => 'OK';

  @override
  String get cycleTrackerTitle => 'चक्र ट्रैकर';

  @override
  String get cycleToday => 'Today';

  @override
  String get cyclePhasePeriod => 'मासिक धर्म';

  @override
  String get cyclePhaseFollicular => 'कूपिक';

  @override
  String get cyclePhaseOvulation => 'ओव्यूलेशन';

  @override
  String get cyclePhaseLuteal => 'ल्यूटियल';

  @override
  String get logFor => 'के लिए लॉग';

  @override
  String get logNone => 'कोई नहीं';

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
  String get logSleep1 => '<5 घंटे';

  @override
  String get logSleep2 => '5-7 घंटे';

  @override
  String get logSleep3 => '7-9 घंटे';

  @override
  String get logSleep4 => '9+ घंटे';

  @override
  String get logSympCramps => 'ऐंठन';

  @override
  String get logSympHeadache => 'सिरदर्द';

  @override
  String get logSympBloating => 'सूजन';

  @override
  String get logSympAcne => 'मुंहासे';

  @override
  String get logLabelEnergy => 'ऊर्जा';

  @override
  String get logLabelSymptoms => 'लक्षण';

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
  String get assistantTitle => 'रिद्मा सहायक';

  @override
  String get assistantSubtitle => 'आपकी स्वास्थ्य सहयोगी • सुरक्षित और निजी';

  @override
  String get assistantInputHint => 'अपना प्रश्न पूछें...';

  @override
  String assistantWelcome(String name) {
    return 'नमस्ते $name 🌸 मैं रिद्मा हूँ, आपकी निजी स्वास्थ्य सहयोगी। अपने मासिक धर्म चक्र, लक्षणों या स्वास्थ्य से जुड़ा कोई भी प्रश्न मुझसे अंग्रेज़ी, हिंदी, मराठी या तमिल में पूछ सकती हैं।';
  }

  @override
  String get assistantSug1 => 'मेरे मासिक धर्म अनियमित क्यों हैं?';

  @override
  String get assistantSug2 => 'गंभीर ऐंठन का क्या कारण है?';

  @override
  String get assistantSug3 => 'क्या 35 दिन का चक्र सामान्य है?';

  @override
  String get assistantSug4 => 'पीएमएस में मदद करने वाले खाद्य पदार्थ';

  @override
  String get assistantSug5 => 'मेरे पीरियड्स अनियमित हैं — क्या यह सामान्य है?';

  @override
  String get assistantDisclaimer =>
      'यह सहायक केवल सामान्य स्वास्थ्य जानकारी प्रदान करता है और यह पेशेवर चिकित्सीय सलाह का विकल्प नहीं है।';

  @override
  String get insightsTitle => 'स्वास्थ्य अंतर्दृष्टि';

  @override
  String get insightsSubtitle => 'पिछले 90 दिन';

  @override
  String get insightsMhsLabel => 'मासिक धर्म स्वास्थ्य स्कोर';

  @override
  String get insightsMhsDelta => 'पिछले चक्र की तुलना में +6';

  @override
  String get insightsVar => 'चक्र परिवर्तनशीलता';

  @override
  String get insightsAvgCycle => 'औसत चक्र';

  @override
  String get insightsRegular => 'नियमित';

  @override
  String get insightsModerate => 'मध्यम';

  @override
  String get insightsTrendLabel => 'चक्र की लंबाई की प्रवृत्ति';

  @override
  String get insightsStabilizing => 'स्थिर हो रहा है';

  @override
  String get insightsHealthy => 'स्वस्थ';

  @override
  String get insightsSymptomsLabel => 'लक्षण पैटर्न';

  @override
  String get insightsMoodSwings => 'मनोदशा में बदलाव';

  @override
  String get insightsWellnessLabel => 'कल्याण सिफारिशें';

  @override
  String get insightsRec1 =>
      'मासिक धर्म शुरू होने के करीब आयरन युक्त खाद्य पदार्थ शामिल करें';

  @override
  String get insightsRec2 => 'ल्यूटियल चरण के दिनों में 10 मिनट का योग आज़माएं';

  @override
  String get insightsRec3 => 'ओव्यूलेशन सप्ताह के दौरान 2.5L पानी पिएं';

  @override
  String get insightsDisclaimer =>
      'ये जानकारियाँ आपके द्वारा दर्ज किए गए डेटा पर आधारित हैं और केवल व्यक्तिगत ट्रैकिंग के लिए हैं। यह चिकित्सीय निदान नहीं है और किसी योग्य स्वास्थ्य विशेषज्ञ की सलाह का विकल्प नहीं है।';

  @override
  String get profileTitle => 'प्रोफ़ाइल';

  @override
  String get profileYearsOld => 'वर्ष';

  @override
  String get profileCycleDay => 'चक्र का दिन';

  @override
  String get profileQuickStats => 'त्वरित आँकड़े';

  @override
  String get profileAvgCycleLength => 'औसत चक्र की लंबाई';

  @override
  String get profileAvgMentalHealth => 'औसत मानसिक स्वास्थ्य';

  @override
  String get profileCycleVariability => 'चक्र परिवर्तनशीलता';

  @override
  String get profileLastCycleLength => 'अंतिम चक्र की लंबाई';

  @override
  String get profileAccountSettings => 'खाता सेटिंग्स';

  @override
  String get profileEditInfo => 'प्रोफ़ाइल जानकारी संपादित करें';

  @override
  String get profileEmergencyContact => 'चिकित्सा आपातकालीन संपर्क';

  @override
  String get profileAppSettings => 'ऐप सेटिंग्स';

  @override
  String get profileEditProfile => 'प्रोफ़ाइल संपादित करें';

  @override
  String get profileName => 'नाम';

  @override
  String get profileAge => 'उम्र';

  @override
  String get profileAvgCycleDays => 'औसत चक्र की लंबाई (दिन)';

  @override
  String get profileSaveChanges => 'परिवर्तन सहेजें';

  @override
  String get profileNameEmptyError => 'Please enter a valid name';

  @override
  String get profileAddContact => 'संपर्क जोड़ें';

  @override
  String get profileEditContact => 'संपर्क संपादित करें';

  @override
  String get profilePhone => 'फ़ोन';

  @override
  String get profileSave => 'सहेजें';

  @override
  String get profileEmergencyContactsTitle => 'आपातकालीन संपर्क';

  @override
  String get profileAddNew => 'नया जोड़ें';

  @override
  String get profileNoContacts =>
      'अभी तक कोई आपातकालीन संपर्क सेट नहीं किया गया है।';

  @override
  String get profileAgeInvalidError => 'कृपया मान्य आयु दर्ज करें';

  @override
  String get profileCycleInvalidError =>
      'कृपया मान्य मासिक चक्र अवधि दर्ज करें';

  @override
  String get profilePhoneInvalidError => 'कृपया मान्य फ़ोन नंबर दर्ज करें';

  @override
  String get contactNameRequiredError => 'Contact name is required';

  @override
  String get edit => 'संपादित करें';

  @override
  String get delete => 'हटाएँ';

  @override
  String get onboardingAvatarOption => 'अवतार विकल्प';

  @override
  String get navHome => 'होम';

  @override
  String get navCycle => 'साइकिल';

  @override
  String get navAsk => 'आस्क';

  @override
  String get navInsights => 'अंतर्दृष्टि';

  @override
  String get navYou => 'यू';

  @override
  String get settingsHelpSupport => 'सहायता और समर्थन';

  @override
  String get settingsContactUs => 'हमसे संपर्क करें / बग की रिपोर्ट करें';

  @override
  String get settingsContactDesc => 'हमारी सहायता टीम को ईमेल करें';

  @override
  String get settingsEmailError =>
      'ईमेल ऐप नहीं खुल सका। कृपया हमें support@rhythma.com पर ईमेल करें';

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
      'आपकी जानकारी आपके डिवाइस पर रहती है। हम आपकी अनुमति के बिना कभी भी आपका डेटा साझा नहीं करते।';

  @override
  String get onboardingNext => 'आगे';

  @override
  String get onboardingBack => 'वापस';

  @override
  String get onboardingSkip => 'छोड़ें';

  @override
  String get onboardingDone => 'शुरू करें';

  @override
  String get onboardingStep1Title => 'अपनी भाषा चुनें';

  @override
  String get onboardingStep1Subtitle => 'वह भाषा चुनें जिसमें आप सबसे सहज हैं';

  @override
  String get onboardingStep2Title => 'अपने बारे में बताएं';

  @override
  String get onboardingStep2Subtitle =>
      'इससे हमें आपका अनुभव व्यक्तिगत बनाने में मदद मिलती है';

  @override
  String get onboardingNameHint => 'आपका नाम या उपनाम';

  @override
  String get onboardingNameLabel => 'नाम';

  @override
  String get onboardingAgeLabel => 'उम्र';

  @override
  String get onboardingHeightLabel => 'ऊंचाई (सेमी)';

  @override
  String get onboardingWeightLabel => 'वज़न (किग्रा)';

  @override
  String get onboardingAvatarLabel => 'अवतार चुनें';

  @override
  String get onboardingStep3Title => 'आपका चक्र';

  @override
  String get onboardingStep3Subtitle =>
      'अपने चक्र के बारे में बताएं — अगर अनिश्चित हों तो छोड़ सकती हैं';

  @override
  String get onboardingLastPeriodLabel => 'पिछले मासिक धर्म की शुरुआत';

  @override
  String get onboardingCycleLengthLabel => 'औसत चक्र अवधि (दिन)';

  @override
  String get onboardingPeriodDurationLabel => 'औसत मासिक धर्म अवधि (दिन)';

  @override
  String get onboardingCycleRegularityLabel => 'चक्र नियमितता';

  @override
  String get onboardingRegular => 'नियमित';

  @override
  String get onboardingIrregular => 'अनियमित';

  @override
  String get onboardingStep4Title => 'थोड़ा और (वैकल्पिक)';

  @override
  String get onboardingStep4Subtitle => 'क्षेत्रीय स्वास्थ्य सुझावों के लिए';

  @override
  String get onboardingPhoneLabel => 'फ़ोन नंबर (वैकल्पिक)';

  @override
  String get onboardingPhoneHint => 'e.g. +919876543210';

  @override
  String get onboardingCityLabel => 'शहर (वैकल्पिक)';

  @override
  String get onboardingStateLabel => 'राज्य / पिन कोड (वैकल्पिक)';

  @override
  String get onboardingStep5Title => 'अपडेट रहें';

  @override
  String get onboardingStep5Subtitle =>
      'सूचनाएं चालू करें ताकि Rhythma सही समय पर याद दिला सके';

  @override
  String get onboardingEnableNotifications => 'चक्र अनुस्मारक सक्षम करें';

  @override
  String get onboardingNotificationsDesc =>
      'मासिक धर्म और ओव्यूलेशन से पहले सौम्य अनुस्मारक पाएं';

  @override
  String get onboardingDataConsentLabel =>
      'मैं इस डिवाइस पर अपना स्वास्थ्य डेटा स्थानीय रूप से संग्रहीत करने की सहमति देती हूं';

  @override
  String get onboardingDataConsentRequired => 'जारी रखने के लिए स्वीकार करें';

  @override
  String get onboardingNameRequired => 'कृपया अपना नाम दर्ज करें';

  @override
  String get onboardingAgeInvalid => 'कृपया वैध आयु दर्ज करें (10–120)';

  @override
  String get onboardingHeightInvalid =>
      'कृपया वैध ऊंचाई दर्ज करें (50–250 सेमी)';

  @override
  String get onboardingWeightInvalid =>
      'कृपया वैध वज़न दर्ज करें (20–300 किग्रा)';

  @override
  String get ayurvedaWellnessTitle => 'आयुर्वेद-प्रेरित स्वास्थ्य जानकारी';

  @override
  String get ayurvedaDisclaimer =>
      'केवल शैक्षिक जानकारी। आयुर्वेद-प्रेरित सामग्री चिकित्सा सलाह, निदान या उपचार नहीं है।';

  @override
  String get ayurvedaMenstrualTitle => 'आराम और आत्मचिंतन';

  @override
  String get ayurvedaMenstrualDescription =>
      'आयुर्वेदिक परंपराएँ मासिक धर्म के समय आराम, आत्मचिंतन और हल्की स्व-देखभाल पर ध्यान देने का वर्णन करती हैं।';

  @override
  String get ayurvedaFollicularTitle => 'नवीनीकरण और गतिविधि';

  @override
  String get ayurvedaFollicularDescription =>
      'आयुर्वेदिक स्वास्थ्य परंपराएँ मासिक धर्म के बाद की अवधि को नवीनीकरण और धीरे-धीरे गतिविधि बढ़ाने से जोड़ती हैं।';

  @override
  String get ayurvedaOvulationTitle => 'संतुलन और जुड़ाव';

  @override
  String get ayurvedaOvulationDescription =>
      'कुछ आयुर्वेदिक परंपराएँ चक्र के मध्य को जीवन शक्ति और सामाजिक जुड़ाव से संबंधित समय के रूप में वर्णित करती हैं।';

  @override
  String get ayurvedaLutealTitle => 'स्थिरता और दिनचर्या';

  @override
  String get ayurvedaLutealDescription =>
      'आयुर्वेदिक स्वास्थ्य परंपराएँ चक्र के बाद के हिस्से में शांत दिनचर्या और जागरूक स्व-देखभाल पर जोर देती हैं।';

  @override
  String get logFlowVeryHeavy => 'Very Heavy';

  @override
  String get logFlowSpotting => 'Spotting';

  @override
  String get logSympSeverePain => 'Severe Pain';

  @override
  String get logSympFainting => 'Fainting';

  @override
  String get smsPhoneHint => '+91 98765 43210';

  @override
  String get smsSummaryMessage =>
      '🌸 Rhythma Health Summary\nThis is your on-demand summary from Rhythma.\nOpen the app for your latest cycle insights.\nReply STOP to unsubscribe.';

  @override
  String get smsSendSectionTitle => 'Send a Summary Now';

  @override
  String get assistantAccessibilityMessageInputHint =>
      'Type your question here';

  @override
  String get onboardingRangeOver65 => 'Over 65';

  @override
  String get onboardingRange150to160 => '150–160 cm';

  @override
  String get insightsNoSymptomsYet =>
      'No symptoms logged yet — log some on the Cycle tab to see patterns here.';

  @override
  String get failedToGetIdToken => 'Failed to get ID token';

  @override
  String get verifying => 'Verifying...';

  @override
  String get deleteAccount => 'Delete Account';

  @override
  String get onboardingRangeUnder150 => 'Under 150 cm';

  @override
  String get pleaseEnterOtp => 'Please enter the OTP.';

  @override
  String get insightsNotEnoughData =>
      'Log a few more cycles on the Cycle tab to unlock your full health insights.';

  @override
  String get smsInfoCardTitle => 'Weekly Health Summary';

  @override
  String get assistantAccessibilitySuggestedPrompt => 'Suggested prompt';

  @override
  String get invalidOtp => 'Invalid OTP. Please try again.';

  @override
  String get deleteAccountConfirmationTitle => 'Delete Account?';

  @override
  String get pleaseEnterPhoneNumber => 'Please enter your phone number.';

  @override
  String get onboardingApproximate3to4Weeks => '3–4 weeks ago';

  @override
  String get onboardingApproximate1to2Weeks => '1–2 weeks ago';

  @override
  String get nudgeCompleteProfileDismiss => 'Maybe later';

  @override
  String get nudgeCompleteProfileTitle => 'Want more accurate predictions?';

  @override
  String get assistantAccessibilitySendMessage => 'Send message';

  @override
  String get onboardingRangeOver180 => 'Over 180 cm';

  @override
  String get smsSendRecipientPrefix => 'Sends the message below to:';

  @override
  String get onboardingRangeUnder50kg => 'Under 50 kg';

  @override
  String get smsErrorInvalidPhone =>
      'Enter a valid phone number in international format, e.g. +919876543210';

  @override
  String insightsLoadError(String error) {
    return 'Couldn\'t load your insights: $error';
  }

  @override
  String get sendingOtp => 'Sending OTP...';

  @override
  String get smsPhoneLabel => 'Phone Number';

  @override
  String get onboardingRange51to65 => '51–65';

  @override
  String get smsSendNoPhone => 'Add and save a phone number above first.';

  @override
  String get enterOtpSentToPhone => 'Enter the OTP sent to your phone';

  @override
  String get onboardingHeightUnit => 'cm';

  @override
  String get getOtp => 'Get OTP';

  @override
  String get nudgeCompleteProfileBody =>
      'Add the exact start date of your last period to improve cycle predictions.';

  @override
  String get onboardingPhoneInvalid =>
      'Use international format, e.g. +919876543210';

  @override
  String get onboardingApproximateLessWeek => 'Less than a week ago';

  @override
  String get onboardingRange171to180 => '171–180 cm';

  @override
  String get smsErrorNetwork =>
      'Couldn\'t reach the server. Check your connection and try again.';

  @override
  String get onboardingRange18to25 => '18–25';

  @override
  String get onboardingRange66to80kg => '66–80 kg';

  @override
  String get smsLoadError =>
      'Couldn\'t load your SMS settings. Pull to refresh or try again.';

  @override
  String get assistantAccessibilitySendMessageHint =>
      'Sends your message to the assistant';

  @override
  String get onboardingRangeUnder18 => 'Under 18';

  @override
  String get onboardingApproximateMoreMonth => 'More than a month ago';

  @override
  String get smsSuccessSaved => 'SMS settings saved successfully!';

  @override
  String get onboardingRange81to100kg => '81–100 kg';

  @override
  String get accountDeletedSuccess => 'Account deleted successfully.';

  @override
  String get onboardingNotSure => 'Not sure';

  @override
  String get phoneNumber => 'Phone Number';

  @override
  String get welcomeToRhythma => 'Welcome to Rhythma';

  @override
  String get onboardingDays => 'days';

  @override
  String get otp => 'OTP';

  @override
  String get insightsNotEnoughTrendData =>
      'Log at least two cycles to see your trend here.';

  @override
  String get smsErrorRateLimit =>
      'You can send one summary per minute, please wait a bit and try again.';

  @override
  String get onboardingTapToSelectDate => 'Tap to select date';

  @override
  String get smsEnableWeekly => 'Enable weekly SMS';

  @override
  String get onboardingLastPeriodRequired =>
      'Please select when your last period started';

  @override
  String get pleaseEnterValidPhoneNumber =>
      'Please enter a valid phone number with country code (e.g., +91).';

  @override
  String get onboardingAgeUnit => 'years';

  @override
  String get smsSuccessSent => 'Summary sent to your phone!';

  @override
  String get onboardingWeightHint => 'Enter your weight';

  @override
  String get onboardingAgeRequired => 'Please enter your age or select a range';

  @override
  String get onboardingRange36to50 => '36–50';

  @override
  String get onboardingRangeOver100kg => 'Over 100 kg';

  @override
  String get languageSelectionError =>
      'Unable to save language. Please try again.';

  @override
  String get loginOrSignUpWithPhone =>
      'Log in or sign up with your phone number.';

  @override
  String get assistantAccessibilityTyping => 'Assistant is typing';

  @override
  String get onboardingWeightRequired =>
      'Please enter your weight or select a range';

  @override
  String otpSentTo(String phone) {
    return 'OTP sent to $phone';
  }

  @override
  String get smsErrorAddPhoneFirst => 'Add and save a phone number first';

  @override
  String get verifyOtp => 'Verify OTP';

  @override
  String get onboardingHeightHint => 'Enter your height';

  @override
  String get onboardingRange161to170 => '161–170 cm';

  @override
  String get verificationFailed => 'Verification failed';

  @override
  String get onboardingApproximateLabel => 'When was your last period?';

  @override
  String get smsErrorGeneric => 'Something went wrong. Please try again.';

  @override
  String get useDifferentPhoneNumber => 'Use a different phone number';

  @override
  String get smsScreenSubtitle => 'Stay informed even without the app';

  @override
  String get onboardingHeightRequired =>
      'Please enter your height or select a range';

  @override
  String get onboardingRange50to65kg => '50–65 kg';

  @override
  String get smsInfoCardBody =>
      'Every week, Rhythma will send you a brief summary of your cycle status, health score, and any important patterns, directly to your phone via SMS. Works without data or the app.';

  @override
  String get smsSendButton => 'Send Summary Now';

  @override
  String get onboardingAgeHint => 'Enter your age';

  @override
  String get nudgeCompleteProfileAction => 'Update';

  @override
  String get onboardingWeightUnit => 'kg';

  @override
  String get smsScreenTitle => 'SMS Summaries';

  @override
  String get onboardingPickExactDate => 'Pick exact date instead';

  @override
  String get smsErrorEnterPhone => 'Please enter a phone number';

  @override
  String get assistantAccessibilityMessageInput => 'Message input';

  @override
  String get smsSaveSettings => 'Save Settings';

  @override
  String get smsErrorSessionExpired =>
      'Your session has expired. Please log in again.';

  @override
  String get langGujarati => 'ગુજરાતી (Gujarati)';

  @override
  String get onboardingApproximate => 'Approximate';

  @override
  String get onboardingRange26to35 => '26–35';

  @override
  String get smsConfigTitle => 'Configuration';

  @override
  String get deleteAccountConfirmationDesc =>
      'This action is permanent and cannot be undone. All your data will be wiped.';
}
