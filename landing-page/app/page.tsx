'use client';

import Image from 'next/image';
import {
  Smartphone,
  Bot,
  Heart,
  BarChart3,
  Lock,
  WifiOff,
  Globe,
  MessageCircle,
  ShieldCheck,
  Code2 as Github,
  ExternalLink,
  BookOpen,
  Download,
  UserPlus,
  PenLine,
  Sparkles,
  ChevronDown,
  Mail,
  FileText,
} from 'lucide-react';

// ── Official Rhythma links ────────────────────────────────────────────────
// Every URL below is a real, already-published Rhythma resource (see the
// project README and the previous landing page). No placeholder URLs, fake
// email addresses, or invented social handles are introduced here.
const LINKS = {
  liveApp: 'https://rhythma-navy.vercel.app',
  repo: 'https://github.com/ishita2740/Rhythma',
  mobileApp: 'https://github.com/ishita2740/Rhythma/tree/main/rhythma_flutter',
  discussions: 'https://github.com/ishita2740/Rhythma/discussions',
  issues: 'https://github.com/ishita2740/Rhythma/issues',
  license: 'https://github.com/ishita2740/Rhythma/blob/main/LICENSE',
  blog: 'https://medium.com/@rathiishita1005729/building-rhythma-an-ai-health-companion-for-the-women-indias-forgot-e249ac1cdc9a',
  linkedin: 'https://www.linkedin.com/company/130984014',
  twitter: 'https://x.com/rhythmaAI',
  instagram: 'https://www.instagram.com/rhythma.ai/',
  email: 'mailto:rhythma.official@gmail.com',
  emailPlain: 'rhythma.official@gmail.com',
};

const FEATURES = [
  {
    icon: Smartphone,
    title: 'Smart Cycle Tracking',
    desc: 'Log periods, flow, mood, sleep and symptoms. Rhythma handles irregular cycles — no fixed 28-day assumption.',
  },
  {
    icon: Bot,
    title: 'AI Health Assistant',
    desc: 'Ask questions about your body in your own language and get educational, grounded answers powered by Google Gemini.',
  },
  {
    icon: BarChart3,
    title: 'Factual Cycle Statistics',
    desc: 'Average, shortest and longest cycle lengths and bleeding duration, computed directly from what you log.',
  },
  {
    icon: Heart,
    title: 'Trends & Consistency',
    desc: 'See how consistent your cycle has been over time, with observations drawn from your own history.',
  },
  {
    icon: Globe,
    title: 'Multilingual by Design',
    desc: 'Built for India first, with translations across many regional languages including Hindi, Marathi, Tamil, Telugu and more.',
  },
  {
    icon: Lock,
    title: 'Privacy First',
    desc: 'On-device storage with encryption at rest. Your health data stays with you unless you choose to sync it.',
  },
  {
    icon: WifiOff,
    title: 'Offline-First',
    desc: 'Core tracking works with zero internet and syncs when you reconnect — made for low-connectivity areas.',
  },
  {
    icon: MessageCircle,
    title: 'SMS Health Summaries',
    desc: 'Receive a summary of your cycle by text message, so the essentials reach you even without the app open.',
  },
];

const STEPS = [
  {
    icon: Download,
    title: 'Discover Rhythma',
    desc: 'Find Rhythma on the web or set up the app from the open-source project — free and India-first.',
  },
  {
    icon: UserPlus,
    title: 'Set up your profile',
    desc: 'Choose your language and share a few basics about your cycle. Everything is optional and private.',
  },
  {
    icon: PenLine,
    title: 'Log your days',
    desc: 'Record periods, flow, mood, sleep and symptoms in seconds — even offline.',
  },
  {
    icon: Sparkles,
    title: 'Understand your health',
    desc: 'Get factual statistics, consistency trends and educational answers from the AI assistant in your language.',
  },
];

const FAQS = [
  {
    q: 'What is Rhythma?',
    a: 'Rhythma is a multilingual, offline-first, AI-powered menstrual and women’s health companion built from the ground up for Indian women. It helps you track your cycle, understand your patterns and ask health questions in your own language.',
  },
  {
    q: 'Who is Rhythma for?',
    a: 'Rhythma is designed for women across India — from teens on their first-period journey to college students and working women managing irregular cycles or PCOD/PCOS awareness, and communities in Tier-2, Tier-3 and semi-urban areas where connectivity and language support are often missing.',
  },
  {
    q: 'Which platforms can I use it on?',
    a: 'Rhythma has a mobile app (Flutter) and a browser-based web experience, both sharing one backend. The project is open source, so you can explore or run either from the GitHub repository. See the Platform access section above for direct links.',
  },
  {
    q: 'Is my data private?',
    a: 'Yes. Rhythma is privacy-first: your data is stored on your device with encryption at rest and processed on-device by default. Nothing leaves your phone unless you explicitly enable cloud sync.',
  },
  {
    q: 'What languages does Rhythma support?',
    a: 'Rhythma is built to support many major Indian languages, including Hindi, Marathi, Tamil, Telugu and more, alongside English — with the goal of expanding coverage across India’s regional languages.',
  },
  {
    q: 'How does the AI assistant work?',
    a: 'The assistant uses Google Gemini to answer questions about menstrual and reproductive health in a compassionate, culturally sensitive way. It provides general educational information only — it does not diagnose conditions or prescribe medication, and it encourages you to consult a professional when appropriate.',
  },
  {
    q: 'Does Rhythma replace a doctor?',
    a: 'No. Rhythma is an educational and preventive health-awareness tool, not a certified medical device. It does not provide medical diagnoses or treatment. Always consult a qualified healthcare professional for medical advice.',
  },
  {
    q: 'How can I contribute or report an issue?',
    a: 'Rhythma is open source and welcomes contributions. You can open issues, join discussions or contribute code through the GitHub repository linked in the footer.',
  },
];

function IconLink({
  href,
  label,
  children,
  external = true,
}: {
  href: string;
  label: string;
  children: React.ReactNode;
  external?: boolean;
}) {
  return (
    <a
      href={href}
      aria-label={label}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      className="text-[#666] hover:text-[#E94B7B] transition text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#E94B7B] rounded"
    >
      {children}
    </a>
  );
}

export default function Page() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#F8F5F2] via-[#FAF9F7] to-[#F5F2ED]">
      {/* Skip link for keyboard/screen-reader users */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[60] focus:bg-white focus:text-[#2D5B6E] focus:px-4 focus:py-2 focus:rounded-full focus:shadow-lg"
      >
        Skip to content
      </a>

      {/* Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-sm bg-[#F8F5F2]/95 border-b border-[#E8DDD5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <a href="#top" className="flex items-center gap-0 focus:outline-none focus:ring-2 focus:ring-[#E94B7B] rounded" aria-label="Rhythma home">
              <div className="w-16 h-16 relative -mr-5">
                <Image src="/logo1.png" alt="Rhythma logo" fill className="object-contain" />
              </div>
              <span className="font-bold text-xl text-[#2D5B6E]">Rhythma</span>
            </a>
            <div className="hidden md:flex items-center gap-7">
              {[
                ['About', '#about'],
                ['Features', '#features'],
                ['How it works', '#how-it-works'],
                ['Platforms', '#platforms'],
                ['Learn', '#learn'],
                ['FAQ', '#faq'],
              ].map(([label, href]) => (
                <a
                  key={href}
                  href={href}
                  className="text-[#5A5A5A] hover:text-[#E94B7B] transition focus:outline-none focus:ring-2 focus:ring-[#E94B7B] rounded text-sm font-medium"
                >
                  {label}
                </a>
              ))}
            </div>
            <a
              href={LINKS.liveApp}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex bg-[#E94B7B] text-white px-5 py-2 rounded-full text-sm font-semibold hover:bg-[#D63A6A] transition focus:outline-none focus:ring-2 focus:ring-[#E94B7B]"
            >
              Open Rhythma
            </a>
          </div>
        </div>
      </nav>

      <main id="main">
        {/* Hero Section */}
        <section id="top" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <span className="inline-block bg-[#FFE8F0] text-[#E94B7B] text-sm font-semibold px-4 py-1.5 rounded-full">
                Her Rhythm. Her Health. Her Power.
              </span>
              <h1 className="text-5xl md:text-6xl font-bold leading-tight">
                <span className="text-[#2D5B6E]">AI for Every Phase</span>
                <br />
                <span className="text-[#E94B7B]">of Her Health</span>
              </h1>
              <p className="text-lg text-[#666] leading-relaxed">
                Rhythma is an AI-powered, multilingual, offline-first women&apos;s health companion
                built from the ground up for India. Track your menstrual cycle, understand your own
                patterns, and get health guidance in your language — with privacy by default.
              </p>
              <div className="flex flex-wrap gap-4 pt-2">
                <a
                  href={LINKS.liveApp}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Open the Rhythma web experience"
                  className="bg-[#E94B7B] text-white px-8 py-3 rounded-full font-semibold hover:bg-[#D63A6A] hover:scale-105 hover:shadow-lg transition-all duration-200 inline-flex items-center gap-2 justify-center focus:outline-none focus:ring-2 focus:ring-[#E94B7B]"
                >
                  Open Rhythma <ExternalLink className="w-4 h-4" />
                </a>
                <a
                  href="#how-it-works"
                  aria-label="Learn how Rhythma works"
                  className="border-2 border-[#E94B7B] text-[#E94B7B] px-8 py-3 rounded-full font-semibold hover:bg-[#FFE8F0] hover:scale-105 hover:shadow-md transition-all duration-200 inline-flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-[#E94B7B]"
                >
                  How it works
                </a>
              </div>
              <div className="flex flex-wrap gap-6 pt-6">
                <IconLink href={LINKS.repo} label="Rhythma on GitHub">GitHub</IconLink>
                <IconLink href={LINKS.linkedin} label="Rhythma on LinkedIn">LinkedIn</IconLink>
                <IconLink href={LINKS.twitter} label="Rhythma on X (Twitter)">Twitter</IconLink>
                <IconLink href={LINKS.instagram} label="Rhythma on Instagram">Instagram</IconLink>
                <IconLink href={LINKS.email} label="Email Rhythma" external={false}>Email</IconLink>
              </div>
            </div>
            <div className="relative h-96 md:h-[500px]">
              <Image
                src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_8NWOzdsTB8KXKc0MgPabkA-YnCpKZ3GwZoeVEZxYfvyNa4a8DYJuH.webp"
                alt="Rhythma dashboard showing menstrual cycle tracking with health metrics and AI insights"
                fill
                className="object-cover rounded-3xl shadow-2xl border-8 border-[#D4A547]/30"
                priority
              />
            </div>
          </div>
        </section>

        {/* About Section */}
        <section id="about" className="bg-[#6B3F7F] text-white py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid md:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-4xl font-bold mb-6">Why Rhythma?</h2>
                <p className="text-lg leading-relaxed mb-5 text-[#E8DDD5]">
                  For millions of women in India, conversations about menstrual health are
                  surrounded by stigma and misinformation. Popular period apps assume English
                  fluency, stable internet and 28-day cycles — assumptions that don&apos;t reflect
                  the reality of Tier-2, Tier-3 and semi-urban India.
                </p>
                <p className="text-lg leading-relaxed mb-6 text-[#E8DDD5]">
                  Rhythma was built from the ground up for Indian women, not adapted from a solution
                  made for another market. Its focus is women&apos;s health and menstrual wellness:
                  enabling earlier awareness, better health literacy and less stigma.
                </p>
                <div className="space-y-3">
                  <p className="flex items-center gap-3">
                    <Globe className="w-5 h-5 text-[#D4A547] shrink-0" strokeWidth={2} /> Multilingual — Hindi, Marathi, Tamil, Telugu and more
                  </p>
                  <p className="flex items-center gap-3">
                    <WifiOff className="w-5 h-5 text-[#D4A547] shrink-0" strokeWidth={2} /> Offline-first, with sync when you reconnect
                  </p>
                  <p className="flex items-center gap-3">
                    <MessageCircle className="w-5 h-5 text-[#D4A547] shrink-0" strokeWidth={2} /> SMS summaries for low-data environments
                  </p>
                  <p className="flex items-center gap-3">
                    <ShieldCheck className="w-5 h-5 text-[#D4A547] shrink-0" strokeWidth={2} /> Privacy and security by default
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                {[
                  ['1 in 5', 'Indian women experience PCOD/PCOS symptoms'],
                  ['~26%', 'of Indian women have regular mobile internet'],
                  ['India-first', 'designed for Indian languages & realities'],
                ].map(([stat, label]) => (
                  <div
                    key={label}
                    className="col-span-3 sm:col-span-1 bg-white/10 rounded-2xl p-6 backdrop-blur-sm border border-white/10"
                  >
                    <div className="text-2xl font-bold text-[#D4A547] mb-2">{stat}</div>
                    <p className="text-sm text-[#E8DDD5] leading-relaxed">{label}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Features Section */}
        <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-[#2D5B6E] mb-4">Everything Rhythma Offers</h2>
            <p className="text-lg text-[#666] max-w-2xl mx-auto">
              Features you can use today — reflecting what the product actually does.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="bg-white p-7 rounded-2xl shadow-sm border border-[#E8DDD5] hover:shadow-lg hover:-translate-y-1 hover:border-[#E94B7B]/30 transition-all duration-300"
              >
                <feature.icon className="w-9 h-9 mb-4 text-[#E94B7B]" strokeWidth={1.75} />
                <h3 className="text-lg font-bold text-[#2D5B6E] mb-2">{feature.title}</h3>
                <p className="text-[#666] leading-relaxed text-sm">{feature.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* AI Assistant highlight */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="relative h-96 md:h-[450px] order-2 md:order-1">
              <Image
                src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_VTIclvoMd2xreJ7H3MeLng-eYaF564KJ4yfeIf2PGiepnJbBSjOCh.webp"
                alt="Rhythma AI assistant interface showing multilingual health guidance"
                fill
                className="object-cover rounded-3xl shadow-2xl border-8 border-[#6B3F7F]/20"
              />
            </div>
            <div className="space-y-6 order-1 md:order-2">
              <h2 className="text-4xl font-bold text-[#2D5B6E]">Powered by AI, Built for India</h2>
              <p className="text-lg text-[#666] leading-relaxed">
                Rhythma&apos;s conversational assistant uses Google Gemini to answer your questions
                in Hindi, Marathi, Tamil or English — clearly, compassionately and grounded in
                sourced references.
              </p>
              <ul className="space-y-4">
                {[
                  'Understands your questions in your language',
                  'Gives educational, general health information',
                  'Respects cultural context and sensitivities',
                  'Guides you toward professional care when needed',
                ].map((item) => (
                  <li key={item} className="flex gap-3 items-start">
                    <span className="text-[#E94B7B] text-xl font-bold leading-6">✓</span>
                    <span className="text-[#666]">{item}</span>
                  </li>
                ))}
              </ul>
              <p className="text-sm text-[#888] italic">
                The assistant provides general wellness information only and is not a substitute for
                professional medical advice.
              </p>
            </div>
          </div>
        </section>

        {/* How Rhythma works */}
        <section id="how-it-works" className="bg-white py-20 border-y border-[#E8DDD5]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold text-[#2D5B6E] mb-4">How Rhythma Works</h2>
              <p className="text-lg text-[#666] max-w-2xl mx-auto">
                From discovering Rhythma to understanding your health — in four simple steps.
              </p>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
              {STEPS.map((step, idx) => (
                <div key={step.title} className="relative text-center px-2">
                  <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-[#FFE8F0] flex items-center justify-center">
                    <step.icon className="w-7 h-7 text-[#E94B7B]" strokeWidth={1.75} />
                  </div>
                  <div className="absolute top-0 left-1/2 -translate-x-1/2 -mt-2 text-xs font-bold text-white bg-[#2D5B6E] rounded-full w-6 h-6 flex items-center justify-center">
                    {idx + 1}
                  </div>
                  <h3 className="text-lg font-bold text-[#2D5B6E] mb-2">{step.title}</h3>
                  <p className="text-[#666] text-sm leading-relaxed">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Platform access */}
        <section id="platforms" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center mb-14">
            <h2 className="text-4xl font-bold text-[#2D5B6E] mb-4">Where to Access Rhythma</h2>
            <p className="text-lg text-[#666] max-w-2xl mx-auto">
              Rhythma is an open-source project with a web experience and a mobile app. Pick the way
              that suits you.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#E8DDD5] flex flex-col">
              <Globe className="w-9 h-9 mb-4 text-[#E94B7B]" strokeWidth={1.75} />
              <h3 className="text-xl font-bold text-[#2D5B6E] mb-2">Web experience</h3>
              <p className="text-[#666] leading-relaxed text-sm mb-6 flex-1">
                Use Rhythma right in your browser — no install needed. Best if you want to get
                started quickly on any device.
              </p>
              <a
                href={LINKS.liveApp}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 bg-[#E94B7B] text-white px-6 py-2.5 rounded-full font-semibold hover:bg-[#D63A6A] transition focus:outline-none focus:ring-2 focus:ring-[#E94B7B]"
              >
                Open web app <ExternalLink className="w-4 h-4" />
              </a>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#E8DDD5] flex flex-col">
              <Smartphone className="w-9 h-9 mb-4 text-[#E94B7B]" strokeWidth={1.75} />
              <h3 className="text-xl font-bold text-[#2D5B6E] mb-2">Mobile app</h3>
              <p className="text-[#666] leading-relaxed text-sm mb-6 flex-1">
                The Flutter app is the primary Rhythma experience with full offline-first tracking.
                Build and run it from the open-source project.
              </p>
              <a
                href={LINKS.mobileApp}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 border-2 border-[#E94B7B] text-[#E94B7B] px-6 py-2.5 rounded-full font-semibold hover:bg-[#FFE8F0] transition focus:outline-none focus:ring-2 focus:ring-[#E94B7B]"
              >
                View the app <Github className="w-4 h-4" />
              </a>
            </div>
            <div className="bg-white p-8 rounded-2xl shadow-sm border border-[#E8DDD5] flex flex-col">
              <Github className="w-9 h-9 mb-4 text-[#E94B7B]" strokeWidth={1.75} />
              <h3 className="text-xl font-bold text-[#2D5B6E] mb-2">Source & community</h3>
              <p className="text-[#666] leading-relaxed text-sm mb-6 flex-1">
                Rhythma is fully open source. Explore the code, follow development, or contribute
                through GitHub.
              </p>
              <a
                href={LINKS.repo}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 border-2 border-[#2D5B6E] text-[#2D5B6E] px-6 py-2.5 rounded-full font-semibold hover:bg-[#2D5B6E]/5 transition focus:outline-none focus:ring-2 focus:ring-[#2D5B6E]"
              >
                Open on GitHub <Github className="w-4 h-4" />
              </a>
            </div>
          </div>
        </section>

        {/* Educational / informational section */}
        <section id="learn" className="bg-[#F0EBFF]/60 py-20 border-y border-[#E8DDD5]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid md:grid-cols-2 gap-12 items-start">
              <div>
                <div className="inline-flex items-center gap-2 bg-white text-[#6B3F7F] text-sm font-semibold px-4 py-1.5 rounded-full mb-5 border border-[#6B3F7F]/15">
                  <BookOpen className="w-4 h-4" /> Learn about your cycle
                </div>
                <h2 className="text-4xl font-bold text-[#2D5B6E] mb-6">Why tracking matters</h2>
                <p className="text-lg text-[#666] leading-relaxed mb-4">
                  Your menstrual cycle is more than your period — it moves through phases
                  (menstrual, follicular, ovulation and luteal) that can affect energy, mood and
                  wellbeing. Tracking helps you notice what&apos;s normal for <em>you</em>, spot
                  changes early, and have more informed conversations with a healthcare provider.
                </p>
                <p className="text-lg text-[#666] leading-relaxed">
                  Rhythma turns your logs into factual statistics and consistency observations — not
                  guesses — so awareness comes from your own data.
                </p>
              </div>
              <div className="space-y-4">
                {[
                  ['Know your phases', 'Understanding the four cycle phases helps you interpret changes in energy, mood and symptoms.'],
                  ['Spot patterns early', 'Consistent logging reveals trends in cycle length and symptoms that are easy to miss day to day.'],
                  ['Reduce stigma', 'Clear, non-judgemental information in your own language makes menstrual health easier to talk about.'],
                ].map(([title, body]) => (
                  <div key={title} className="bg-white p-6 rounded-2xl border border-[#E8DDD5]">
                    <h3 className="font-bold text-[#2D5B6E] mb-1.5">{title}</h3>
                    <p className="text-[#666] text-sm leading-relaxed">{body}</p>
                  </div>
                ))}
                <div className="bg-[#FFF7E6] border border-[#D4A547]/40 rounded-2xl p-6 flex gap-3">
                  <ShieldCheck className="w-6 h-6 text-[#D4A547] shrink-0" strokeWidth={2} />
                  <p className="text-sm text-[#7A6320] leading-relaxed">
                    <strong>Health disclaimer:</strong> Rhythma is an educational and preventive
                    health-awareness tool. It is not a certified medical device and does not provide
                    diagnoses, prescriptions or treatment. Always consult a qualified healthcare
                    professional for medical advice.
                  </p>
                </div>
                <a
                  href={LINKS.blog}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-[#E94B7B] font-semibold hover:underline focus:outline-none focus:ring-2 focus:ring-[#E94B7B] rounded"
                >
                  Read the Rhythma story <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ section */}
        <section id="faq" className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center mb-14">
            <h2 className="text-4xl font-bold text-[#2D5B6E] mb-4">Frequently Asked Questions</h2>
            <p className="text-lg text-[#666]">Everything you might want to know about Rhythma.</p>
          </div>
          <div className="space-y-4">
            {FAQS.map((faq) => (
              <details
                key={faq.q}
                className="group bg-white rounded-2xl border border-[#E8DDD5] overflow-hidden [&_summary::-webkit-details-marker]:hidden"
              >
                <summary className="flex items-center justify-between gap-4 cursor-pointer list-none px-6 py-5 font-semibold text-[#2D5B6E] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#E94B7B] rounded-2xl">
                  <span>{faq.q}</span>
                  <ChevronDown className="w-5 h-5 text-[#E94B7B] shrink-0 transition-transform duration-200 group-open:rotate-180" />
                </summary>
                <div className="px-6 pb-5 -mt-1 text-[#666] leading-relaxed">{faq.a}</div>
              </details>
            ))}
          </div>
        </section>

        {/* CTA Section */}
        <section id="contact" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 pb-24">
          <div className="bg-gradient-to-r from-[#E94B7B] to-[#D63A6A] rounded-3xl p-12 text-center text-white">
            <h2 className="text-4xl font-bold mb-4">Ready to understand your health?</h2>
            <p className="text-xl mb-8 max-w-2xl mx-auto text-white/90">
              Open Rhythma in your browser, explore the open-source project, or reach out — we&apos;d
              love to hear from you.
            </p>
            <div className="flex flex-wrap gap-4 justify-center">
              <a
                href={LINKS.liveApp}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-white text-[#E94B7B] px-8 py-3 rounded-full font-bold hover:bg-[#F0F0F0] hover:scale-105 hover:shadow-lg transition-all duration-200 inline-flex items-center gap-2"
              >
                Open Rhythma <ExternalLink className="w-4 h-4" />
              </a>
              <a
                href={LINKS.repo}
                target="_blank"
                rel="noopener noreferrer"
                className="border-2 border-white text-white px-8 py-3 rounded-full font-bold hover:bg-white/10 hover:scale-105 transition-all duration-200 inline-flex items-center gap-2"
              >
                Explore on GitHub <Github className="w-4 h-4" />
              </a>
              <a
                href={LINKS.email}
                className="border-2 border-white text-white px-8 py-3 rounded-full font-bold hover:bg-white/10 hover:scale-105 transition-all duration-200 inline-flex items-center gap-2"
              >
                Email us <Mail className="w-4 h-4" />
              </a>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-[#2D5B6E] text-white py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-10 mb-10">
            <div>
              <div className="flex items-center gap-0 mb-3">
                <div className="w-12 h-12 relative -mr-3">
                  <Image src="/logo1.png" alt="Rhythma logo" fill className="object-contain" />
                </div>
                <span className="font-bold text-lg">Rhythma</span>
              </div>
              <p className="text-[#B0D4E3] text-sm leading-relaxed">
                AI for every phase of her health. Multilingual, offline-first, privacy-first
                women&apos;s health — built for India.
              </p>
            </div>
            <div>
              <h4 className="font-bold mb-4">Explore</h4>
              <ul className="space-y-2 text-[#B0D4E3] text-sm">
                <li><a href="#about" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">About</a></li>
                <li><a href="#features" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Features</a></li>
                <li><a href="#how-it-works" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">How it works</a></li>
                <li><a href="#platforms" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Platforms</a></li>
                <li><a href="#faq" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">FAQ</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold mb-4">Project</h4>
              <ul className="space-y-2 text-[#B0D4E3] text-sm">
                <li><a href={LINKS.liveApp} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Web experience</a></li>
                <li><a href={LINKS.repo} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">GitHub repository</a></li>
                <li><a href={LINKS.discussions} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Discussions</a></li>
                <li><a href={LINKS.blog} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Blog</a></li>
                <li><a href={LINKS.license} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded"><FileText className="w-3.5 h-3.5" /> MIT License</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold mb-4">Connect</h4>
              <ul className="space-y-2 text-[#B0D4E3] text-sm">
                <li><a href={LINKS.twitter} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Twitter / X</a></li>
                <li><a href={LINKS.linkedin} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">LinkedIn</a></li>
                <li><a href={LINKS.instagram} target="_blank" rel="noopener noreferrer" className="hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded">Instagram</a></li>
                <li><a href={LINKS.email} className="inline-flex items-center gap-1.5 hover:text-white transition focus:outline-none focus:ring-2 focus:ring-white rounded"><Mail className="w-3.5 h-3.5" /> {LINKS.emailPlain}</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-[#4A7F9E] pt-8 text-center text-[#B0D4E3] text-sm">
            <p>
              &copy; {new Date().getFullYear()} Rhythma. Licensed under MIT. | Educational tool — not
              a medical device. Not a substitute for professional medical advice.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
