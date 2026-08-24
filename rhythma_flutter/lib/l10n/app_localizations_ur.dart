// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Urdu (`ur`).
class AppLocalizationsUr extends AppLocalizations {
  AppLocalizationsUr([String locale = 'ur']) : super(locale);

  @override
  String get appTitle => 'Rhythma';

  @override
  String get settingsTitle => 'ترتیبات';

  @override
  String get appPreferences => 'ایپ کی ترجیحات';

  @override
  String get languagePreferences => 'زبان کی ترجیحات';

  @override
  String get darkMode => 'ڈارک موڈ';

  @override
  String get themeToggle => 'تھیم ٹوگل';

  @override
  String get notificationsTitle => 'اطلاعات';

  @override
  String get cycleTrackingReminders => 'سائیکل ٹریکنگ یاد دہانیاں';

  @override
  String get medicineAlerts => 'دوا کے الرٹس';

  @override
  String get wellnessTips => 'صحت کے مشورے';

  @override
  String get securityPrivacyTitle => 'سیکیورٹی اور پرائیویسی';

  @override
  String get appPermissions => 'ایپ کی اجازتیں';

  @override
  String get privacyPolicy => 'پرائیویسی پالیسی';

  @override
  String get logOut => 'لاگ آؤٹ';

  @override
  String get logoutConfirmation => 'کیا آپ واقعی Rhythma سے لاگ آؤٹ کرنا چاہتے ہیں؟';

  @override
  String get cancel => 'منسوخ کریں';

  @override
  String get loggedOutSuccess => 'کامیابی سے لاگ آؤٹ ہو گیا';

  @override
  String get selectLanguage => 'زبان منتخب کریں';

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
  String get homeGreeting => 'آداب';

  @override
  String get homePhaseDesc => 'دن 14 · اوولیشن کا مرحلہ';

  @override
  String get homeNextPeriod => 'اگلا ماہواری';

  @override
  String get homeDaysLabel => 'دن';

  @override
  String get homeFertileWindow => 'زرخیز وقت · ';

  @override
  String get homeHighEnergy => 'اعلی توانائی';

  @override
  String get homeFertileWindowDisclaimer =>
      'This is an estimate based on your logged data, not medical or contraceptive advice.';

  @override
  String get homeAiTitle => 'RHYTHMA AI';

  @override
  String get homeAiSubtitle => 'اپنے جسم کے بارے میں کچھ بھی پوچھیں،\nاپنی زبان میں۔';

  @override
  String get homeAiPrompt => 'میری ماہواری بے قاعدہ کیوں ہے؟';

  @override
  String get homeFeelingTitle => 'آج آپ کیسا محسوس کر رہی ہیں؟';

  @override
  String get homeLogAll => 'سب لاگ کریں';

  @override
  String get homeLogFlow => 'بہاؤ';

  @override
  String get homeLogMood => 'مزاج';

  @override
  String get homeLogSleep => 'نیند';

  @override
  String get homeLogStress => 'ذہنی تناؤ';

  @override
  String get homeWeeklyInsightLabel => 'ہفتہ وار بصیرت';

  @override
  String get homeWeeklyInsightTitle => 'اس ہفتے آپ کی نیند میں 12% بہتری آئی — آپ کا سائیکل شکر گزار ہو سکتا ہے۔';

  @override
  String get homeWeeklyInsightDesc => 'اوولیشن سے پہلے مسلسل آرام ہارمونل توازن کی حمایت کرتا ہے۔';

  @override
  String get homeLearnTitle => 'Rhythma کے ساتھ سیکھیں';

  @override
  String get homeLearnPcos => 'PCOS کو سمجھنا';

  @override
  String get homeLearnHormones => 'ہارمونز کی بنیادی باتیں';

  @override
  String get homeLearnIron => 'آئرن سے بھرپور غذائیں';

  @override
  String get homeArticle => 'مضمون';

  @override
  String get homeFailedLoad => 'ڈیش بورڈ لوڈ کرنے میں ناکام';

  @override
  String get homeRetry => 'دوبارہ کوشش کریں';

  @override
  String get notificationPeriodTitle => 'Period expected soon';

  @override
  String notificationPeriodBody(String days) {
    return 'Your period is expected in about $days days. A good time to get what you need ready.';
  }

  @override
  String get notificationLogPeriodTitle => 'Let\'s get your cycle back on track';

  @override
  String get notificationLogPeriodBody => 'It\'s been a while since you logged a period, so we can\'t predict the next one. Open Rhythma and log your last period.';

  @override
  String get notificationLogReminderTitle => 'Time to log your day';

  @override
  String get notificationLogReminderBody => 'You haven\'t logged anything today. A moment now makes your predictions better.';

  @override
  String get notificationChannelReminders => 'Rhythma reminders';

  @override
  String get homeMhs => 'MHS';

  @override
  String get homeCvi => 'CVI';

  @override
  String get homeSleep => 'نیند';

  @override
  String get homeComingSoon => 'جلد آرہا ہے';

  @override
  String homeUnderDevelopment(String topic) {
    return '\$\\1 فی الحال زیر تکمیل ہے۔';
  }

  @override
  String get homeErrorNetwork => 'براہ کرم اپنا انٹرنیٹ کنکشن چیک کریں اور دوبارہ کوشش کریں۔';

  @override
  String get homeErrorAuth => 'آپ کا سیشن ختم ہو گیا ہے۔ براہ کرم دوبارہ لاگ ان کریں۔';

  @override
  String get homeErrorServer => 'ہماری طرف کچھ غلط ہو گیا۔ براہ کرم بعد میں دوبارہ کوشش کریں۔';

  @override
  String get homeErrorGeneric => 'ڈیٹا لوڈ کرنے سے قاصر۔ براہ کرم دوبارہ کوشش کریں۔';

  @override
  String homeQuickLogTitle(String label) {
    return 'لاگ کریں \$\\1';
  }

  @override
  String homeQuickLogSaved(String label, String value) {
    return '\$\\1 لاگ ہو گیا: \$\\1';
  }

  @override
  String get homePrivacySecurity => 'پرائیویسی اور سیکیورٹی';

  @override
  String get homeOk => 'ٹھیک ہے';

  @override
  String get cycleTrackerTitle => 'سائیکل ٹریکر';

  @override
  String get cycleToday => 'آج';

  @override
  String get cyclePhasePeriod => 'ماہواری';

  @override
  String get cyclePhaseFollicular => 'فولیکولر';

  @override
  String get cyclePhaseOvulation => 'اوولیشن';

  @override
  String get cyclePhaseLuteal => 'لیوٹیل';

  @override
  String get logFor => 'کے لیے لاگ کریں';

  @override
  String get logNone => 'کچھ نہیں';

  @override
  String get logLight => 'ہلکا';

  @override
  String get logMedium => 'درمیانہ';

  @override
  String get logHeavy => 'زیادہ';

  @override
  String get logEnergyLow => 'کم';

  @override
  String get logEnergyMid => 'درمیانی';

  @override
  String get logEnergyHigh => 'زیادہ';

  @override
  String get logSleep1 => '<5گھنٹے';

  @override
  String get logSleep2 => '5-7گھنٹے';

  @override
  String get logSleep3 => '7-9گھنٹے';

  @override
  String get logSleep4 => '9گھنٹے+';

  @override
  String get logSympCramps => 'درد';

  @override
  String get logSympHeadache => 'سر درد';

  @override
  String get logSympBloating => 'پیٹ پھولنا';

  @override
  String get logSympAcne => 'مہاسے';

  @override
  String get logLabelEnergy => 'توانائی';

  @override
  String get logLabelSymptoms => 'علامات';

  @override
  String get logToday => 'آج لاگ کریں';

  @override
  String get logTitle => 'اپنا دن لاگ کریں';

  @override
  String get logFlowIntensity => 'بہاؤ کی شدت';

  @override
  String get logMood => 'مزاج';

  @override
  String get logSleepHours => 'نیند کے گھنٹے';

  @override
  String get logStressLevel => 'ذہنی تناؤ کی سطح';

  @override
  String get logSave => 'لاگ محفوظ کریں';

  @override
  String get logSympFatigue => 'تھکاوٹ';

  @override
  String get logSympNausea => 'متلی';

  @override
  String get logSympBackPain => 'کمر درد';

  @override
  String get assistantTitle => 'Rhythma اسسٹنٹ';

  @override
  String get assistantSubtitle => 'آپ کا نجی صحت کا ساتھی';

  @override
  String get assistantInputHint => 'اپنی صحت کے بارے میں کچھ بھی پوچھیں...';

  @override
  String assistantWelcome(String name) {
    return 'ہیلو \$\\1 🌸 میں Rhythma ہوں، آپ کا نجی صحت کا ساتھی۔ مجھ سے اپنے سائیکل، علامات یا صحت کے بارے میں کچھ بھی پوچھیں۔';
  }

  @override
  String get assistantSug1 => 'میری ماہواری بے قاعدہ کیوں ہے؟';

  @override
  String get assistantSug2 => 'شدید درد کی کیا وجوہات ہیں؟';

  @override
  String get assistantSug3 => 'کیا 35 دن کا سائیکل نارمل ہے؟';

  @override
  String get assistantSug4 => 'غذائیں جو PMS میں مدد کرتی ہیں';

  @override
  String get assistantSug5 => 'میرے پیریڈز بے قاعدہ ہیں — کیا یہ نارمل ہے؟';

  @override
  String get assistantDisclaimer =>
      'This assistant provides general wellness information only and is not a substitute for professional medical advice.';

  @override
  String get insightsTitle => 'صحت کی بصیرت';

  @override
  String get insightsSubtitle => 'پچھلے 90 دن';

  @override
  String get insightsMhsLabel => 'حیض کی صحت کا سکور';

  @override
  String get insightsMhsDelta => 'پچھلے سائیکل کے مقابلے میں +6';

  @override
  String get insightsVar => 'سائیکل کی تبدیلی';

  @override
  String get insightsAvgCycle => 'اوسط سائیکل';

  @override
  String get insightsRegular => 'باقاعدہ';

  @override
  String get insightsModerate => 'درمیانہ';

  @override
  String get insightsTrendLabel => 'سائیکل کی لمبائی کا رجحان';

  @override
  String get insightsStabilizing => 'مستحکم ہو رہا ہے';

  @override
  String get insightsHealthy => 'صحت مند';

  @override
  String get insightsSymptomsLabel => 'علامات کے نمونے';

  @override
  String get insightsMoodSwings => 'مزاج میں تبدیلی';

  @override
  String get insightsWellnessLabel => 'صحت کی سفارشات';

  @override
  String get insightsRec1 => 'ماہواری شروع ہونے کے قریب آئرن والی غذائیں شامل کریں';

  @override
  String get insightsRec2 => 'لیوٹیل مرحلے کے دنوں میں 10 منٹ کا یوگا آزمائیں';

  @override
  String get insightsRec3 => 'اوولیشن والے ہفتے میں 2.5 لیٹر پانی پیئں';

  @override
  String get insightsDisclaimer =>
      'These insights are based on the information you log and are intended for personal tracking only. They are not a medical diagnosis and should not replace advice from a qualified healthcare professional.';

  @override
  String get profileTitle => 'پروفائل';

  @override
  String get profileYearsOld => 'سال کی عمر';

  @override
  String get profileCycleDay => 'سائیکل کا دن';

  @override
  String get profileQuickStats => 'فوری اعدادوشمار';

  @override
  String get profileAvgCycleLength => 'اوسط سائیکل کی لمبائی';

  @override
  String get profileAvgMentalHealth => 'اوسط ذہنی صحت';

  @override
  String get profileCycleVariability => 'سائیکل کی تبدیلی';

  @override
  String get profileLastCycleLength => 'آخری سائیکل کی لمبائی';

  @override
  String get profileAccountSettings => 'اکاؤنٹ کی ترتیبات';

  @override
  String get profileEditInfo => 'پروفائل کی معلومات میں ترمیم کریں';

  @override
  String get profileEmergencyContact => 'طبی ہنگامی رابطہ';

  @override
  String get profileAppSettings => 'ایپ کی ترتیبات';

  @override
  String get profileEditProfile => 'پروفائل میں ترمیم کریں';

  @override
  String get profileName => 'نام';

  @override
  String get profileAge => 'عمر';

  @override
  String get profileAvgCycleDays => 'اوسط سائیکل کی لمبائی (دن)';

  @override
  String get profileSaveChanges => 'تبدیلیاں محفوظ کریں';

  @override
  String get profileNameEmptyError => 'براہ کرم ایک درست نام درج کریں';

  @override
  String get profileAddContact => 'رابطہ شامل کریں';

  @override
  String get profileEditContact => 'رابطے میں ترمیم کریں';

  @override
  String get profilePhone => 'فون';

  @override
  String get profileSave => 'محفوظ کریں';

  @override
  String get profileEmergencyContactsTitle => 'ہنگامی رابطے';

  @override
  String get profileAddNew => 'نیا شامل کریں';

  @override
  String get profileNoContacts => 'ابھی تک کوئی ہنگامی رابطہ قائم نہیں کیا گیا۔';

  @override
  String get profileAgeInvalidError => 'براہ کرم ایک درست عمر درج کریں';

  @override
  String get profileCycleInvalidError => 'براہ کرم ایک درست سائیکل کی لمبائی درج کریں';

  @override
  String get profilePhoneInvalidError => 'براہ کرم ایک درست فون نمبر درج کریں';

  @override
  String get contactNameRequiredError => 'رابطے کا نام درکار ہے';

  @override
  String get edit => 'ترمیم کریں';

  @override
  String get delete => 'حذف کریں';

  @override
  String get onboardingAvatarOption => 'اوتار کا اختیار';

  @override
  String get navHome => 'ہوم';

  @override
  String get navCycle => 'سائیکل';

  @override
  String get navAsk => 'پوچھیں';

  @override
  String get navInsights => 'بصیرت';

  @override
  String get navYou => 'آپ';

  @override
  String get settingsHelpSupport => 'مدد اور تعاون';

  @override
  String get settingsContactUs => 'ہم سے رابطہ کریں / بگ رپورٹ کریں';

  @override
  String get settingsContactDesc => 'ہماری سپورٹ ٹیم کو ای میل بھیجیں';

  @override
  String get settingsEmailError => 'ای میل ایپ نہیں کھل سکی۔ براہ کرم support@rhythma.com پر ہمیں ای میل کریں۔';

  @override
  String get settingsData => 'ڈیٹا';

  @override
  String get settingsExportData => 'میرا ڈیٹا ایکسپورٹ کریں';

  @override
  String get settingsExportDataDesc => 'اپنا پروفائل، رابطے اور سائیکل لاگز JSON کے طور پر ڈاؤن لوڈ کریں';

  @override
  String get settingsExportSuccess => 'ڈیٹا کامیابی سے ایکسپورٹ ہو گیا';

  @override
  String get onboardingPrivacyNote => 'آپ کی معلومات آپ کے آلے پر رہتی ہیں۔ ہم آپ کی اجازت کے بغیر کبھی آپ کا ڈیٹا شیئر نہیں کرتے۔';

  @override
  String get onboardingNext => 'آگے';

  @override
  String get onboardingBack => 'پیچھے';

  @override
  String get onboardingSkip => 'چھوڑیں';

  @override
  String get onboardingDone => 'شروع کریں';

  @override
  String get onboardingStep1Title => 'اپنی زبان منتخب کریں';

  @override
  String get onboardingStep1Subtitle => 'وہ زبان منتخب کریں جس میں آپ سب سے زیادہ آرام دہ ہیں';

  @override
  String get onboardingStep2Title => 'اپنے بارے میں بتائیں';

  @override
  String get onboardingStep2Subtitle => 'اس سے ہمیں آپ کے تجربے کو ذاتی بنانے میں مدد ملتی ہے';

  @override
  String get onboardingNameHint => 'آپ کا نام یا عرفی نام';

  @override
  String get onboardingNameLabel => 'نام';

  @override
  String get onboardingAgeLabel => 'عمر';

  @override
  String get onboardingHeightLabel => 'قد (سینٹی میٹر)';

  @override
  String get onboardingWeightLabel => 'وزن (کلوگرام)';

  @override
  String get onboardingAvatarLabel => 'ایک اوتار منتخب کریں';

  @override
  String get onboardingStep3Title => 'آپ کا سائیکل';

  @override
  String get onboardingStep3Subtitle => 'اپنے سائیکل کو سمجھنے میں ہماری مدد کریں — اگر یقین نہ ہو تو آپ چھوڑ سکتے ہیں';

  @override
  String get onboardingLastPeriodLabel => 'آخری ماہواری شروع ہونے کی تاریخ';

  @override
  String get onboardingCycleLengthLabel => 'اوسط سائیکل کی لمبائی (دن)';

  @override
  String get onboardingPeriodDurationLabel => 'اوسط ماہواری کا دورانیہ (دن)';

  @override
  String get onboardingCycleRegularityLabel => 'سائیکل کی باقاعدگی';

  @override
  String get onboardingRegular => 'باقاعدہ';

  @override
  String get onboardingIrregular => 'بے قاعدہ';

  @override
  String get onboardingStep4Title => 'تھوڑا اور (اختیاری)';

  @override
  String get onboardingStep4Subtitle => 'علاقے کے مخصوص صحت کے مشورے تجویز کرنے میں ہماری مدد کرتا ہے';

  @override
  String get onboardingPhoneLabel => 'فون نمبر (اختیاری)';

  @override
  String get onboardingPhoneHint => 'مثلاً +919876543210';

  @override
  String get onboardingCityLabel => 'شہر (اختیاری)';

  @override
  String get onboardingStateLabel => 'ریاست / پن کوڈ (اختیاری)';

  @override
  String get onboardingStep5Title => 'باخبر رہیں';

  @override
  String get onboardingStep5Subtitle => 'اطلاعات کو فعال کریں تاکہ Rhythma آپ کو صحیح وقت پر یاد دلائے';

  @override
  String get onboardingEnableNotifications => 'سائیکل کی یاد دہانیاں فعال کریں';

  @override
  String get onboardingNotificationsDesc => 'اپنی ماہواری اور اوولیشن ونڈو سے پہلے ہلکی یاد دہانیاں حاصل کریں';

  @override
  String get onboardingDataConsentLabel => 'میں اس آلے پر اپنا صحت کا ڈیٹا مقامی طور پر محفوظ کرنے کی رضامندی دیتا/دیتی ہوں';

  @override
  String get onboardingDataConsentRequired => 'جاری رکھنے کے لیے براہ کرم قبول کریں';

  @override
  String get onboardingNameRequired => 'براہ کرم اپنا نام درج کریں';

  @override
  String get onboardingAgeInvalid => 'براہ کرم ایک درست عمر درج کریں (10-120)';

  @override
  String get onboardingHeightInvalid => 'براہ کرم ایک درست قد درج کریں (50-250 سینٹی میٹر)';

  @override
  String get onboardingWeightInvalid => 'براہ کرم ایک درست وزن درج کریں (20-300 کلوگرام)';

  @override
  String get onboardingPhoneInvalid => 'بین الاقوامی فارمیٹ استعمال کریں، مثلاً +919876543210';

  @override
  String get onboardingAgeRequired => 'براہ کرم اپنی عمر درج کریں یا حد منتخب کریں';

  @override
  String get onboardingHeightRequired => 'براہ کرم اپنا قد درج کریں یا حد منتخب کریں';

  @override
  String get onboardingWeightRequired => 'براہ کرم اپنا وزن درج کریں یا حد منتخب کریں';

  @override
  String get onboardingNotSure => 'یقین نہیں';

  @override
  String get onboardingApproximate => 'اندازاََ';

  @override
  String get onboardingAgeHint => 'اپنی عمر درج کریں';

  @override
  String get onboardingAgeUnit => 'سال';

  @override
  String get onboardingHeightHint => 'اپنا قد درج کریں';

  @override
  String get onboardingHeightUnit => 'سینٹی میٹر';

  @override
  String get onboardingWeightHint => 'اپنا وزن درج کریں';

  @override
  String get onboardingWeightUnit => 'کلوگرام';

  @override
  String get onboardingRangeUnder18 => '18 سے کم';

  @override
  String get onboardingRange18to25 => '18-25';

  @override
  String get onboardingRange26to35 => '26-35';

  @override
  String get onboardingRange36to50 => '36-50';

  @override
  String get onboardingRange51to65 => '51-65';

  @override
  String get onboardingRangeOver65 => '65 سے زیادہ';

  @override
  String get onboardingRangeUnder150 => '150 سینٹی میٹر سے کم';

  @override
  String get onboardingRange150to160 => '150-160 سینٹی میٹر';

  @override
  String get onboardingRange161to170 => '161-170 سینٹی میٹر';

  @override
  String get onboardingRange171to180 => '171-180 سینٹی میٹر';

  @override
  String get onboardingRangeOver180 => '180 سینٹی میٹر سے زیادہ';

  @override
  String get onboardingRangeUnder50kg => '50 کلوگرام سے کم';

  @override
  String get onboardingRange50to65kg => '50-65 کلوگرام';

  @override
  String get onboardingRange66to80kg => '66-80 کلوگرام';

  @override
  String get onboardingRange81to100kg => '81-100 کلوگرام';

  @override
  String get onboardingRangeOver100kg => '100 کلوگرام سے زیادہ';

  @override
  String get onboardingTapToSelectDate => 'تاریخ منتخب کرنے کے لیے ٹیپ کریں';

  @override
  String get onboardingDays => 'دن';

  @override
  String get onboardingApproximateLabel => 'آپ کی آخری ماہواری کب تھی؟';

  @override
  String get onboardingApproximateLessWeek => 'ایک ہفتے سے کم پہلے';

  @override
  String get onboardingApproximate1to2Weeks => '1-2 ہفتے پہلے';

  @override
  String get onboardingApproximate3to4Weeks => '3-4 ہفتے پہلے';

  @override
  String get onboardingApproximateMoreMonth => 'ایک مہینے سے زیادہ پہلے';

  @override
  String get onboardingPickExactDate => 'اس کے بجائے صحیح تاریخ منتخب کریں';

  @override
  String get onboardingLastPeriodRequired => 'براہ کرم منتخب کریں کہ آپ کی آخری ماہواری کب شروع ہوئی';

  @override
  String get nudgeCompleteProfileTitle => 'مزید درست پیشین گوئیاں چاہتے ہیں؟';

  @override
  String get nudgeCompleteProfileBody => 'سائیکل کی پیشین گوئیوں کو بہتر بنانے کے لیے اپنی آخری ماہواری کے شروع ہونے کی صحیح تاریخ شامل کریں۔';

  @override
  String get nudgeCompleteProfileAction => 'اپ ڈیٹ کریں';

  @override
  String get nudgeCompleteProfileDismiss => 'شاید بعد میں';

  @override
  String get smsScreenTitle => 'SMS خلاصے';

  @override
  String get smsScreenSubtitle => 'ایپ کے بغیر بھی باخبر رہیں';

  @override
  String get smsInfoCardTitle => 'ہفتہ وار صحت کا خلاصہ';

  @override
  String get smsInfoCardBody => 'ہر ہفتے، Rhythma آپ کو آپ کے سائیکل کی صورتحال، صحت کے سکور اور اہم نمونوں کا ایک مختصر خلاصہ SMS کے ذریعے آپ کے فون پر بھیجے گا۔ یہ ڈیٹا یا ایپ کے بغیر کام کرتا ہے۔';

  @override
  String get smsConfigTitle => 'کنفیگریشن';

  @override
  String get smsPhoneLabel => 'فون نمبر';

  @override
  String get smsPhoneHint => '+91 98765 43210';

  @override
  String get smsEnableWeekly => 'ہفتہ وار SMS فعال کریں';

  @override
  String get smsSaveSettings => 'ترتیبات محفوظ کریں';

  @override
  String get smsSendSectionTitle => 'ابھی خلاصہ بھیجیں';

  @override
  String get smsSendRecipientPrefix => 'نیچے دیا گیا پیغام بھیجتا ہے کو:';

  @override
  String get smsSendNoPhone => 'پہلے اوپر ایک فون نمبر شامل اور محفوظ کریں۔';

  @override
  String get smsSendButton => 'ابھی خلاصہ بھیجیں';

  @override
  String get smsErrorEnterPhone => 'براہ کرم ایک فون نمبر درج کریں';

  @override
  String get smsErrorInvalidPhone => 'بین الاقوامی فارمیٹ میں ایک درست فون نمبر درج کریں، مثلاً +919876543210';

  @override
  String get smsSuccessSaved => 'SMS کی ترتیبات کامیابی سے محفوظ ہو گئیں!';

  @override
  String get smsErrorAddPhoneFirst => 'پہلے ایک فون نمبر شامل اور محفوظ کریں';

  @override
  String get smsSuccessSent => 'خلاصہ آپ کے فون پر بھیج دیا گیا!';

  @override
  String get smsErrorRateLimit => 'آپ ایک منٹ میں ایک خلاصہ بھیج سکتے ہیں، براہ کرم تھوڑا انتظار کریں اور دوبارہ کوشش کریں۔';

  @override
  String get smsErrorSessionExpired => 'آپ کا سیشن ختم ہو گیا ہے۔ براہ کرم دوبارہ لاگ ان کریں۔';

  @override
  String get smsErrorNetwork => 'سرور تک رسائی حاصل نہیں کی جا سکی۔ اپنا کنکشن چیک کریں اور دوبارہ کوشش کریں۔';

  @override
  String get smsErrorGeneric => 'کچھ غلط ہو گیا۔ براہ کرم دوبارہ کوشش کریں۔';

  @override
  String get smsLoadError => 'آپ کی SMS کی ترتیبات لوڈ نہیں ہو سکیں۔ ریفریش کرنے کے لیے کھینچیں یا دوبارہ کوشش کریں۔';

  @override
  String get smsSummaryMessage => '🌸 Rhythma صحت کا خلاصہ\nیہ Rhythma کی طرف سے آپ کی مانگ پر خلاصہ ہے۔\nاپنے تازہ ترین سائیکل کی بصیرت کے لیے ایپ کھولیں۔\nرکنیت ختم کرنے کے لیے STOP کا جواب دیں۔';

  @override
  String insightsLoadError(String error) {
    return 'آپ کی بصیرت لوڈ نہیں کی جا سکی: \$\\1';
  }

  @override
  String get insightsNotEnoughData => 'اپنی صحت کی مکمل بصیرت کو غیر مقفل کرنے کے لیے سائیکل ٹیب پر مزید کچھ سائیکل لاگ کریں۔';

  @override
  String get insightsNoSymptomsYet => 'ابھی تک کوئی علامات لاگ نہیں کی گئیں — یہاں نمونے دیکھنے کے لیے سائیکل ٹیب پر کچھ لاگ کریں۔';

  @override
  String get insightsNotEnoughTrendData => 'یہاں اپنا رجحان دیکھنے کے لیے کم از کم دو سائیکل لاگ کریں۔';

  @override
  String get assistantAccessibilitySuggestedPrompt => 'تجویز کردہ پرامپٹ';

  @override
  String get assistantAccessibilityMessageInput => 'پیغام کا ان پٹ';

  @override
  String get assistantAccessibilityMessageInputHint => 'اپنا سوال یہاں ٹائپ کریں';

  @override
  String get assistantAccessibilitySendMessage => 'پیغام بھیجیں';

  @override
  String get assistantAccessibilitySendMessageHint => 'آپ کا پیغام اسسٹنٹ کو بھیجتا ہے';

  @override
  String get assistantAccessibilityTyping => 'اسسٹنٹ ٹائپ کر رہا ہے';

  @override
  String get languageSelectionError => 'زبان محفوظ کرنے سے قاصر۔ براہ کرم دوبارہ کوشش کریں۔';

  @override
  String get deleteAccount => 'اکاؤنٹ حذف کریں';

  @override
  String get deleteAccountConfirmationTitle => 'اکاؤنٹ حذف کریں؟';

  @override
  String get deleteAccountConfirmationDesc => 'یہ عمل مستقل ہے اور اسے کالعدم نہیں کیا جا سکتا۔ آپ کا سارا ڈیٹا مٹا دیا جائے گا۔';

  @override
  String get accountDeletedSuccess => 'اکاؤنٹ کامیابی سے حذف ہو گیا۔';

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
}
