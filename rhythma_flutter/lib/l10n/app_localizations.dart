import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_hi.dart';
import 'app_localizations_mr.dart';
import 'app_localizations_ta.dart';
import 'app_localizations_te.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('hi'),
    Locale('mr'),
    Locale('ta'),
    Locale('te')
  ];

  /// The title of the application
  ///
  /// In en, this message translates to:
  /// **'Rhythma'**
  String get appTitle;

  /// No description provided for @settingsTitle.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settingsTitle;

  /// No description provided for @appPreferences.
  ///
  /// In en, this message translates to:
  /// **'App Preferences'**
  String get appPreferences;

  /// No description provided for @languagePreferences.
  ///
  /// In en, this message translates to:
  /// **'Language Preferences'**
  String get languagePreferences;

  /// No description provided for @darkMode.
  ///
  /// In en, this message translates to:
  /// **'Dark Mode'**
  String get darkMode;

  /// No description provided for @themeToggle.
  ///
  /// In en, this message translates to:
  /// **'Theme toggle'**
  String get themeToggle;

  /// No description provided for @notificationsTitle.
  ///
  /// In en, this message translates to:
  /// **'Notifications'**
  String get notificationsTitle;

  /// No description provided for @cycleTrackingReminders.
  ///
  /// In en, this message translates to:
  /// **'Cycle Tracking Reminders'**
  String get cycleTrackingReminders;

  /// No description provided for @medicineAlerts.
  ///
  /// In en, this message translates to:
  /// **'Medicine Alerts'**
  String get medicineAlerts;

  /// No description provided for @wellnessTips.
  ///
  /// In en, this message translates to:
  /// **'Wellness Tips'**
  String get wellnessTips;

  /// No description provided for @securityPrivacyTitle.
  ///
  /// In en, this message translates to:
  /// **'Security & Privacy'**
  String get securityPrivacyTitle;

  /// No description provided for @appPermissions.
  ///
  /// In en, this message translates to:
  /// **'App Permissions'**
  String get appPermissions;

  /// No description provided for @privacyPolicy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get privacyPolicy;

  /// No description provided for @logOut.
  ///
  /// In en, this message translates to:
  /// **'Log Out'**
  String get logOut;

  /// No description provided for @logoutConfirmation.
  ///
  /// In en, this message translates to:
  /// **'Are you sure you want to log out of Rhythma?'**
  String get logoutConfirmation;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @loggedOutSuccess.
  ///
  /// In en, this message translates to:
  /// **'Logged out successfully'**
  String get loggedOutSuccess;

  /// No description provided for @selectLanguage.
  ///
  /// In en, this message translates to:
  /// **'Select Language'**
  String get selectLanguage;

  /// No description provided for @homeGreeting.
  ///
  /// In en, this message translates to:
  /// **'Namaste'**
  String get homeGreeting;

  /// No description provided for @homePhaseDesc.
  ///
  /// In en, this message translates to:
  /// **'Day 14 · Ovulation phase'**
  String get homePhaseDesc;

  /// No description provided for @homeNextPeriod.
  ///
  /// In en, this message translates to:
  /// **'NEXT PERIOD IN'**
  String get homeNextPeriod;

  /// No description provided for @homeDaysLabel.
  ///
  /// In en, this message translates to:
  /// **'days'**
  String get homeDaysLabel;

  /// No description provided for @homeFertileWindow.
  ///
  /// In en, this message translates to:
  /// **'Fertile window · '**
  String get homeFertileWindow;

  /// No description provided for @homeHighEnergy.
  ///
  /// In en, this message translates to:
  /// **'High energy'**
  String get homeHighEnergy;

  /// No description provided for @homeAiTitle.
  ///
  /// In en, this message translates to:
  /// **'RHYTHMA AI'**
  String get homeAiTitle;

  /// No description provided for @homeAiSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Ask me anything about your body,\nin your language.'**
  String get homeAiSubtitle;

  /// No description provided for @homeAiPrompt.
  ///
  /// In en, this message translates to:
  /// **'Why are my periods irregular?'**
  String get homeAiPrompt;

  /// No description provided for @homeFeelingTitle.
  ///
  /// In en, this message translates to:
  /// **'How are you feeling today?'**
  String get homeFeelingTitle;

  /// No description provided for @homeLogAll.
  ///
  /// In en, this message translates to:
  /// **'Log all'**
  String get homeLogAll;

  /// No description provided for @homeLogFlow.
  ///
  /// In en, this message translates to:
  /// **'Flow'**
  String get homeLogFlow;

  /// No description provided for @homeLogMood.
  ///
  /// In en, this message translates to:
  /// **'Mood'**
  String get homeLogMood;

  /// No description provided for @homeLogSleep.
  ///
  /// In en, this message translates to:
  /// **'Sleep'**
  String get homeLogSleep;

  /// No description provided for @homeLogStress.
  ///
  /// In en, this message translates to:
  /// **'Stress'**
  String get homeLogStress;

  /// No description provided for @homeWeeklyInsightLabel.
  ///
  /// In en, this message translates to:
  /// **'WEEKLY INSIGHT'**
  String get homeWeeklyInsightLabel;

  /// No description provided for @homeWeeklyInsightTitle.
  ///
  /// In en, this message translates to:
  /// **'Your sleep improved 12% this week — your cycle may thank you.'**
  String get homeWeeklyInsightTitle;

  /// No description provided for @homeWeeklyInsightDesc.
  ///
  /// In en, this message translates to:
  /// **'Consistent rest before ovulation supports hormonal balance.'**
  String get homeWeeklyInsightDesc;

  /// No description provided for @homeLearnTitle.
  ///
  /// In en, this message translates to:
  /// **'Learn with Rhythma'**
  String get homeLearnTitle;

  /// No description provided for @homeLearnPcos.
  ///
  /// In en, this message translates to:
  /// **'Understanding PCOS'**
  String get homeLearnPcos;

  /// No description provided for @homeLearnHormones.
  ///
  /// In en, this message translates to:
  /// **'Hormones 101'**
  String get homeLearnHormones;

  /// No description provided for @homeLearnIron.
  ///
  /// In en, this message translates to:
  /// **'Iron-rich foods'**
  String get homeLearnIron;

  /// No description provided for @homeArticle.
  ///
  /// In en, this message translates to:
  /// **'ARTICLE'**
  String get homeArticle;

  /// No description provided for @homeFailedLoad.
  ///
  /// In en, this message translates to:
  /// **'Failed to load dashboard'**
  String get homeFailedLoad;

  /// No description provided for @homeRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get homeRetry;

  /// No description provided for @homeComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Coming Soon'**
  String get homeComingSoon;

  /// No description provided for @homeUnderDevelopment.
  ///
  /// In en, this message translates to:
  /// **'{topic} is currently under development.'**
  String homeUnderDevelopment(String topic);

  /// No description provided for @homePrivacySecurity.
  ///
  /// In en, this message translates to:
  /// **'Privacy & Security'**
  String get homePrivacySecurity;

  /// No description provided for @homeOk.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get homeOk;

  /// No description provided for @cycleTrackerTitle.
  ///
  /// In en, this message translates to:
  /// **'Cycle Tracker'**
  String get cycleTrackerTitle;

  /// No description provided for @cyclePhasePeriod.
  ///
  /// In en, this message translates to:
  /// **'Period'**
  String get cyclePhasePeriod;

  /// No description provided for @cyclePhaseFollicular.
  ///
  /// In en, this message translates to:
  /// **'Follicular'**
  String get cyclePhaseFollicular;

  /// No description provided for @cyclePhaseOvulation.
  ///
  /// In en, this message translates to:
  /// **'Ovulation'**
  String get cyclePhaseOvulation;

  /// No description provided for @cyclePhaseLuteal.
  ///
  /// In en, this message translates to:
  /// **'Luteal'**
  String get cyclePhaseLuteal;

  /// No description provided for @logFor.
  ///
  /// In en, this message translates to:
  /// **'Log for'**
  String get logFor;

  /// No description provided for @logNone.
  ///
  /// In en, this message translates to:
  /// **'None'**
  String get logNone;

  /// No description provided for @logLight.
  ///
  /// In en, this message translates to:
  /// **'Light'**
  String get logLight;

  /// No description provided for @logMedium.
  ///
  /// In en, this message translates to:
  /// **'Medium'**
  String get logMedium;

  /// No description provided for @logHeavy.
  ///
  /// In en, this message translates to:
  /// **'Heavy'**
  String get logHeavy;

  /// No description provided for @logEnergyLow.
  ///
  /// In en, this message translates to:
  /// **'Low'**
  String get logEnergyLow;

  /// No description provided for @logEnergyMid.
  ///
  /// In en, this message translates to:
  /// **'Mid'**
  String get logEnergyMid;

  /// No description provided for @logEnergyHigh.
  ///
  /// In en, this message translates to:
  /// **'High'**
  String get logEnergyHigh;

  /// No description provided for @logSleep1.
  ///
  /// In en, this message translates to:
  /// **'<5h'**
  String get logSleep1;

  /// No description provided for @logSleep2.
  ///
  /// In en, this message translates to:
  /// **'5-7h'**
  String get logSleep2;

  /// No description provided for @logSleep3.
  ///
  /// In en, this message translates to:
  /// **'7-9h'**
  String get logSleep3;

  /// No description provided for @logSleep4.
  ///
  /// In en, this message translates to:
  /// **'9h+'**
  String get logSleep4;

  /// No description provided for @logSympCramps.
  ///
  /// In en, this message translates to:
  /// **'Cramps'**
  String get logSympCramps;

  /// No description provided for @logSympHeadache.
  ///
  /// In en, this message translates to:
  /// **'Headache'**
  String get logSympHeadache;

  /// No description provided for @logSympBloating.
  ///
  /// In en, this message translates to:
  /// **'Bloating'**
  String get logSympBloating;

  /// No description provided for @logSympAcne.
  ///
  /// In en, this message translates to:
  /// **'Acne'**
  String get logSympAcne;

  /// No description provided for @logLabelEnergy.
  ///
  /// In en, this message translates to:
  /// **'Energy'**
  String get logLabelEnergy;

  /// No description provided for @logLabelSymptoms.
  ///
  /// In en, this message translates to:
  /// **'Symptoms'**
  String get logLabelSymptoms;

  /// No description provided for @logToday.
  ///
  /// In en, this message translates to:
  /// **'Log Today'**
  String get logToday;

  /// No description provided for @logTitle.
  ///
  /// In en, this message translates to:
  /// **'Log your day'**
  String get logTitle;

  /// No description provided for @logFlowIntensity.
  ///
  /// In en, this message translates to:
  /// **'Flow Intensity'**
  String get logFlowIntensity;

  /// No description provided for @logMood.
  ///
  /// In en, this message translates to:
  /// **'Mood'**
  String get logMood;

  /// No description provided for @logSleepHours.
  ///
  /// In en, this message translates to:
  /// **'Sleep Hours'**
  String get logSleepHours;

  /// No description provided for @logStressLevel.
  ///
  /// In en, this message translates to:
  /// **'Stress Level'**
  String get logStressLevel;

  /// No description provided for @logSave.
  ///
  /// In en, this message translates to:
  /// **'Save Log'**
  String get logSave;

  /// No description provided for @logSympFatigue.
  ///
  /// In en, this message translates to:
  /// **'Fatigue'**
  String get logSympFatigue;

  /// No description provided for @logSympNausea.
  ///
  /// In en, this message translates to:
  /// **'Nausea'**
  String get logSympNausea;

  /// No description provided for @logSympBackPain.
  ///
  /// In en, this message translates to:
  /// **'Back Pain'**
  String get logSympBackPain;

  /// No description provided for @assistantTitle.
  ///
  /// In en, this message translates to:
  /// **'Rhythma Assistant'**
  String get assistantTitle;

  /// No description provided for @assistantSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Your private health companion'**
  String get assistantSubtitle;

  /// No description provided for @assistantInputHint.
  ///
  /// In en, this message translates to:
  /// **'Ask anything about your health...'**
  String get assistantInputHint;

  /// No description provided for @assistantWelcome.
  ///
  /// In en, this message translates to:
  /// **'Hi Aarya 🌸 I\'m Rhythma, your private health companion. Ask me anything about your cycle, symptoms, or wellbeing — in English, Hindi, Marathi, or Tamil.'**
  String get assistantWelcome;

  /// No description provided for @assistantSug1.
  ///
  /// In en, this message translates to:
  /// **'Why are my periods irregular?'**
  String get assistantSug1;

  /// No description provided for @assistantSug2.
  ///
  /// In en, this message translates to:
  /// **'What causes severe cramps?'**
  String get assistantSug2;

  /// No description provided for @assistantSug3.
  ///
  /// In en, this message translates to:
  /// **'Is a 35-day cycle normal?'**
  String get assistantSug3;

  /// No description provided for @assistantSug4.
  ///
  /// In en, this message translates to:
  /// **'Foods that help with PMS'**
  String get assistantSug4;

  /// No description provided for @assistantSug5.
  ///
  /// In en, this message translates to:
  /// **'मेरे पीरियड्स अनियमित हैं — क्या यह सामान्य है?'**
  String get assistantSug5;

  /// No description provided for @insightsTitle.
  ///
  /// In en, this message translates to:
  /// **'Health Insights'**
  String get insightsTitle;

  /// No description provided for @insightsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Last 90 days'**
  String get insightsSubtitle;

  /// No description provided for @insightsMhsLabel.
  ///
  /// In en, this message translates to:
  /// **'MENSTRUAL HEALTH SCORE'**
  String get insightsMhsLabel;

  /// No description provided for @insightsMhsDelta.
  ///
  /// In en, this message translates to:
  /// **'+6 vs last cycle'**
  String get insightsMhsDelta;

  /// No description provided for @insightsVar.
  ///
  /// In en, this message translates to:
  /// **'Cycle Variability'**
  String get insightsVar;

  /// No description provided for @insightsAvgCycle.
  ///
  /// In en, this message translates to:
  /// **'Avg Cycle'**
  String get insightsAvgCycle;

  /// No description provided for @insightsRegular.
  ///
  /// In en, this message translates to:
  /// **'Regular'**
  String get insightsRegular;

  /// No description provided for @insightsModerate.
  ///
  /// In en, this message translates to:
  /// **'Moderate'**
  String get insightsModerate;

  /// No description provided for @insightsTrendLabel.
  ///
  /// In en, this message translates to:
  /// **'CYCLE LENGTH TREND'**
  String get insightsTrendLabel;

  /// No description provided for @insightsStabilizing.
  ///
  /// In en, this message translates to:
  /// **'Stabilizing'**
  String get insightsStabilizing;

  /// No description provided for @insightsHealthy.
  ///
  /// In en, this message translates to:
  /// **'Healthy'**
  String get insightsHealthy;

  /// No description provided for @insightsSymptomsLabel.
  ///
  /// In en, this message translates to:
  /// **'Symptom patterns'**
  String get insightsSymptomsLabel;

  /// No description provided for @insightsMoodSwings.
  ///
  /// In en, this message translates to:
  /// **'Mood swings'**
  String get insightsMoodSwings;

  /// No description provided for @insightsWellnessLabel.
  ///
  /// In en, this message translates to:
  /// **'Wellness recommendations'**
  String get insightsWellnessLabel;

  /// No description provided for @insightsRec1.
  ///
  /// In en, this message translates to:
  /// **'Add iron-rich foods near period start'**
  String get insightsRec1;

  /// No description provided for @insightsRec2.
  ///
  /// In en, this message translates to:
  /// **'Try 10-minute yoga on luteal-phase days'**
  String get insightsRec2;

  /// No description provided for @insightsRec3.
  ///
  /// In en, this message translates to:
  /// **'Hydrate 2.5L during ovulation week'**
  String get insightsRec3;

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profileTitle;

  /// No description provided for @profileYearsOld.
  ///
  /// In en, this message translates to:
  /// **'years old'**
  String get profileYearsOld;

  /// No description provided for @profileCycleDay.
  ///
  /// In en, this message translates to:
  /// **'Cycle Day'**
  String get profileCycleDay;

  /// No description provided for @profileQuickStats.
  ///
  /// In en, this message translates to:
  /// **'Quick Stats'**
  String get profileQuickStats;

  /// No description provided for @profileAvgCycleLength.
  ///
  /// In en, this message translates to:
  /// **'Avg Cycle Length'**
  String get profileAvgCycleLength;

  /// No description provided for @profileAvgMentalHealth.
  ///
  /// In en, this message translates to:
  /// **'Avg Mental Health'**
  String get profileAvgMentalHealth;

  /// No description provided for @profileCycleVariability.
  ///
  /// In en, this message translates to:
  /// **'Cycle Variability'**
  String get profileCycleVariability;

  /// No description provided for @profileLastCycleLength.
  ///
  /// In en, this message translates to:
  /// **'Last Cycle Length'**
  String get profileLastCycleLength;

  /// No description provided for @profileAccountSettings.
  ///
  /// In en, this message translates to:
  /// **'Account Settings'**
  String get profileAccountSettings;

  /// No description provided for @profileEditInfo.
  ///
  /// In en, this message translates to:
  /// **'Edit Profile Information'**
  String get profileEditInfo;

  /// No description provided for @profileEmergencyContact.
  ///
  /// In en, this message translates to:
  /// **'Medical Emergency Contact'**
  String get profileEmergencyContact;

  /// No description provided for @profileAppSettings.
  ///
  /// In en, this message translates to:
  /// **'App Settings'**
  String get profileAppSettings;

  /// No description provided for @profileEditProfile.
  ///
  /// In en, this message translates to:
  /// **'Edit Profile'**
  String get profileEditProfile;

  /// No description provided for @profileName.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get profileName;

  /// No description provided for @profileAge.
  ///
  /// In en, this message translates to:
  /// **'Age'**
  String get profileAge;

  /// No description provided for @profileAvgCycleDays.
  ///
  /// In en, this message translates to:
  /// **'Average Cycle Length (Days)'**
  String get profileAvgCycleDays;

  /// No description provided for @profileSaveChanges.
  ///
  /// In en, this message translates to:
  /// **'Save Changes'**
  String get profileSaveChanges;

  /// No description provided for @profileAddContact.
  ///
  /// In en, this message translates to:
  /// **'Add Contact'**
  String get profileAddContact;

  /// No description provided for @profileEditContact.
  ///
  /// In en, this message translates to:
  /// **'Edit Contact'**
  String get profileEditContact;

  /// No description provided for @profilePhone.
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get profilePhone;

  /// No description provided for @profileSave.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get profileSave;

  /// No description provided for @profileEmergencyContactsTitle.
  ///
  /// In en, this message translates to:
  /// **'Emergency Contacts'**
  String get profileEmergencyContactsTitle;

  /// No description provided for @profileAddNew.
  ///
  /// In en, this message translates to:
  /// **'Add New'**
  String get profileAddNew;

  /// No description provided for @profileNoContacts.
  ///
  /// In en, this message translates to:
  /// **'No emergency contacts set up yet.'**
  String get profileNoContacts;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navCycle.
  ///
  /// In en, this message translates to:
  /// **'Cycle'**
  String get navCycle;

  /// No description provided for @navAsk.
  ///
  /// In en, this message translates to:
  /// **'Ask'**
  String get navAsk;

  /// No description provided for @navInsights.
  ///
  /// In en, this message translates to:
  /// **'Insights'**
  String get navInsights;

  /// No description provided for @navYou.
  ///
  /// In en, this message translates to:
  /// **'You'**
  String get navYou;

  /// No description provided for @settingsHelpSupport.
  ///
  /// In en, this message translates to:
  /// **'Help & Support'**
  String get settingsHelpSupport;

  /// No description provided for @settingsContactUs.
  ///
  /// In en, this message translates to:
  /// **'Contact Us / Report Bug'**
  String get settingsContactUs;

  /// No description provided for @settingsContactDesc.
  ///
  /// In en, this message translates to:
  /// **'Send an email to our support team'**
  String get settingsContactDesc;

  /// No description provided for @settingsEmailError.
  ///
  /// In en, this message translates to:
  /// **'Could not open email app. Please email us at support@rhythma.com'**
  String get settingsEmailError;

  /// No description provided for @onboardingPrivacyNote.
  ///
  /// In en, this message translates to:
  /// **'Your information stays on your device. We never share your data without your permission.'**
  String get onboardingPrivacyNote;

  /// No description provided for @onboardingNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get onboardingNext;

  /// No description provided for @onboardingBack.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get onboardingBack;

  /// No description provided for @onboardingSkip.
  ///
  /// In en, this message translates to:
  /// **'Skip'**
  String get onboardingSkip;

  /// No description provided for @onboardingDone.
  ///
  /// In en, this message translates to:
  /// **'Get Started'**
  String get onboardingDone;

  /// No description provided for @onboardingStep1Title.
  ///
  /// In en, this message translates to:
  /// **'Choose Your Language'**
  String get onboardingStep1Title;

  /// No description provided for @onboardingStep1Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Select the language you are most comfortable with'**
  String get onboardingStep1Subtitle;

  /// No description provided for @onboardingStep2Title.
  ///
  /// In en, this message translates to:
  /// **'Tell us about you'**
  String get onboardingStep2Title;

  /// No description provided for @onboardingStep2Subtitle.
  ///
  /// In en, this message translates to:
  /// **'This helps us personalise your experience'**
  String get onboardingStep2Subtitle;

  /// No description provided for @onboardingNameHint.
  ///
  /// In en, this message translates to:
  /// **'Your name or nickname'**
  String get onboardingNameHint;

  /// No description provided for @onboardingNameLabel.
  ///
  /// In en, this message translates to:
  /// **'Name'**
  String get onboardingNameLabel;

  /// No description provided for @onboardingAgeLabel.
  ///
  /// In en, this message translates to:
  /// **'Age'**
  String get onboardingAgeLabel;

  /// No description provided for @onboardingHeightLabel.
  ///
  /// In en, this message translates to:
  /// **'Height (cm)'**
  String get onboardingHeightLabel;

  /// No description provided for @onboardingWeightLabel.
  ///
  /// In en, this message translates to:
  /// **'Weight (kg)'**
  String get onboardingWeightLabel;

  /// No description provided for @onboardingAvatarLabel.
  ///
  /// In en, this message translates to:
  /// **'Choose an Avatar'**
  String get onboardingAvatarLabel;

  /// No description provided for @onboardingStep3Title.
  ///
  /// In en, this message translates to:
  /// **'Your Cycle'**
  String get onboardingStep3Title;

  /// No description provided for @onboardingStep3Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Help us understand your cycle — you can skip if unsure'**
  String get onboardingStep3Subtitle;

  /// No description provided for @onboardingLastPeriodLabel.
  ///
  /// In en, this message translates to:
  /// **'Last Period Start Date'**
  String get onboardingLastPeriodLabel;

  /// No description provided for @onboardingCycleLengthLabel.
  ///
  /// In en, this message translates to:
  /// **'Average Cycle Length (days)'**
  String get onboardingCycleLengthLabel;

  /// No description provided for @onboardingPeriodDurationLabel.
  ///
  /// In en, this message translates to:
  /// **'Average Period Duration (days)'**
  String get onboardingPeriodDurationLabel;

  /// No description provided for @onboardingCycleRegularityLabel.
  ///
  /// In en, this message translates to:
  /// **'Cycle Regularity'**
  String get onboardingCycleRegularityLabel;

  /// No description provided for @onboardingRegular.
  ///
  /// In en, this message translates to:
  /// **'Regular'**
  String get onboardingRegular;

  /// No description provided for @onboardingIrregular.
  ///
  /// In en, this message translates to:
  /// **'Irregular'**
  String get onboardingIrregular;

  /// No description provided for @onboardingStep4Title.
  ///
  /// In en, this message translates to:
  /// **'A Little More (Optional)'**
  String get onboardingStep4Title;

  /// No description provided for @onboardingStep4Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Helps us suggest region-specific wellness tips'**
  String get onboardingStep4Subtitle;

  /// No description provided for @onboardingPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Phone Number (optional)'**
  String get onboardingPhoneLabel;

  /// No description provided for @onboardingCityLabel.
  ///
  /// In en, this message translates to:
  /// **'City (optional)'**
  String get onboardingCityLabel;

  /// No description provided for @onboardingStateLabel.
  ///
  /// In en, this message translates to:
  /// **'State / PIN Code (optional)'**
  String get onboardingStateLabel;

  /// No description provided for @onboardingStep5Title.
  ///
  /// In en, this message translates to:
  /// **'Stay in the loop'**
  String get onboardingStep5Title;

  /// No description provided for @onboardingStep5Subtitle.
  ///
  /// In en, this message translates to:
  /// **'Enable notifications so Rhythma can remind you at the right time'**
  String get onboardingStep5Subtitle;

  /// No description provided for @onboardingEnableNotifications.
  ///
  /// In en, this message translates to:
  /// **'Enable Cycle Reminders'**
  String get onboardingEnableNotifications;

  /// No description provided for @onboardingNotificationsDesc.
  ///
  /// In en, this message translates to:
  /// **'Get gentle reminders before your period and ovulation window'**
  String get onboardingNotificationsDesc;

  /// No description provided for @onboardingDataConsentLabel.
  ///
  /// In en, this message translates to:
  /// **'I consent to storing my health data locally on this device'**
  String get onboardingDataConsentLabel;

  /// No description provided for @onboardingDataConsentRequired.
  ///
  /// In en, this message translates to:
  /// **'Please accept to continue'**
  String get onboardingDataConsentRequired;

  /// No description provided for @onboardingNameRequired.
  ///
  /// In en, this message translates to:
  /// **'Please enter your name'**
  String get onboardingNameRequired;

  /// No description provided for @onboardingAgeInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid age (10–120)'**
  String get onboardingAgeInvalid;

  /// No description provided for @onboardingHeightInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid height (50–250 cm)'**
  String get onboardingHeightInvalid;

  /// No description provided for @onboardingWeightInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid weight (20–300 kg)'**
  String get onboardingWeightInvalid;

  /// No description provided for @onboardingPhoneInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid phone number'**
  String get onboardingPhoneInvalid;

  /// No description provided for @onboardingTapToSelectDate.
  ///
  /// In en, this message translates to:
  /// **'Tap to select date'**
  String get onboardingTapToSelectDate;

  /// No description provided for @onboardingDays.
  ///
  /// In en, this message translates to:
  /// **'days'**
  String get onboardingDays;

  /// No description provided for @smsScreenTitle.
  ///
  /// In en, this message translates to:
  /// **'SMS Summaries'**
  String get smsScreenTitle;

  /// No description provided for @smsScreenSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Stay informed even without the app'**
  String get smsScreenSubtitle;

  /// No description provided for @smsInfoCardTitle.
  ///
  /// In en, this message translates to:
  /// **'Weekly Health Summary'**
  String get smsInfoCardTitle;

  /// No description provided for @smsInfoCardBody.
  ///
  /// In en, this message translates to:
  /// **'Every week, Rhythma will send you a brief summary of your cycle status, health score, and any important patterns, directly to your phone via SMS. Works without data or the app.'**
  String get smsInfoCardBody;

  /// No description provided for @smsConfigTitle.
  ///
  /// In en, this message translates to:
  /// **'Configuration'**
  String get smsConfigTitle;

  /// No description provided for @smsPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Phone Number'**
  String get smsPhoneLabel;

  /// No description provided for @smsPhoneHint.
  ///
  /// In en, this message translates to:
  /// **'+91 98765 43210'**
  String get smsPhoneHint;

  /// No description provided for @smsEnableWeekly.
  ///
  /// In en, this message translates to:
  /// **'Enable weekly SMS'**
  String get smsEnableWeekly;

  /// No description provided for @smsSaveSettings.
  ///
  /// In en, this message translates to:
  /// **'Save Settings'**
  String get smsSaveSettings;

  /// No description provided for @smsSendSectionTitle.
  ///
  /// In en, this message translates to:
  /// **'Send a Summary Now'**
  String get smsSendSectionTitle;

  /// No description provided for @smsSendRecipientPrefix.
  ///
  /// In en, this message translates to:
  /// **'Sends the message below to:'**
  String get smsSendRecipientPrefix;

  /// No description provided for @smsSendNoPhone.
  ///
  /// In en, this message translates to:
  /// **'Add and save a phone number above first.'**
  String get smsSendNoPhone;

  /// No description provided for @smsSendButton.
  ///
  /// In en, this message translates to:
  /// **'Send Summary Now'**
  String get smsSendButton;

  /// No description provided for @smsErrorEnterPhone.
  ///
  /// In en, this message translates to:
  /// **'Please enter a phone number'**
  String get smsErrorEnterPhone;

  /// No description provided for @smsErrorInvalidPhone.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid phone number in international format, e.g. +919876543210'**
  String get smsErrorInvalidPhone;

  /// No description provided for @smsSuccessSaved.
  ///
  /// In en, this message translates to:
  /// **'SMS settings saved successfully!'**
  String get smsSuccessSaved;

  /// No description provided for @smsErrorAddPhoneFirst.
  ///
  /// In en, this message translates to:
  /// **'Add and save a phone number first'**
  String get smsErrorAddPhoneFirst;

  /// No description provided for @smsSuccessSent.
  ///
  /// In en, this message translates to:
  /// **'Summary sent to your phone!'**
  String get smsSuccessSent;

  /// No description provided for @smsErrorRateLimit.
  ///
  /// In en, this message translates to:
  /// **'You can send one summary per minute, please wait a bit and try again.'**
  String get smsErrorRateLimit;

  /// No description provided for @smsErrorSessionExpired.
  ///
  /// In en, this message translates to:
  /// **'Your session has expired. Please log in again.'**
  String get smsErrorSessionExpired;

  /// No description provided for @smsErrorNetwork.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t reach the server. Check your connection and try again.'**
  String get smsErrorNetwork;

  /// No description provided for @smsErrorGeneric.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong. Please try again.'**
  String get smsErrorGeneric;

  /// No description provided for @smsLoadError.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t load your SMS settings. Pull to refresh or try again.'**
  String get smsLoadError;

  /// No description provided for @smsSummaryMessage.
  ///
  /// In en, this message translates to:
  /// **'🌸 Rhythma Health Summary\nThis is your on-demand summary from Rhythma.\nOpen the app for your latest cycle insights.\nReply STOP to unsubscribe.'**
  String get smsSummaryMessage;

  /// No description provided for @insightsLoadError.
  ///
  /// In en, this message translates to:
  /// **'Couldn\'t load your insights: {error}'**
  String insightsLoadError(String error);

  /// No description provided for @insightsNotEnoughData.
  ///
  /// In en, this message translates to:
  /// **'Log a few more cycles on the Cycle tab to unlock your full health insights.'**
  String get insightsNotEnoughData;

  /// No description provided for @insightsNoSymptomsYet.
  ///
  /// In en, this message translates to:
  /// **'No symptoms logged yet — log some on the Cycle tab to see patterns here.'**
  String get insightsNoSymptomsYet;

  /// No description provided for @insightsNotEnoughTrendData.
  ///
  /// In en, this message translates to:
  /// **'Log at least two cycles to see your trend here.'**
  String get insightsNotEnoughTrendData;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'hi', 'mr', 'ta', 'te'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'hi':
      return AppLocalizationsHi();
    case 'mr':
      return AppLocalizationsMr();
    case 'ta':
      return AppLocalizationsTa();
    case 'te':
      return AppLocalizationsTe();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
