'use client';

import { useState } from 'react';
import Image from 'next/image';

export default function Page() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) {
      setSubmitted(true);
      setEmail('');
      setTimeout(() => setSubmitted(false), 3000);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#F8F5F2] via-[#FAF9F7] to-[#F5F2ED]">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-sm bg-[#F8F5F2]/95 border-b border-[#E8DDD5]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-[#2D5B6E] via-[#8B5B9E] to-[#D4A547] rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">R</span>
              </div>
              <span className="font-bold text-xl text-[#2D5B6E]">Rhythma</span>
            </div>
            <div className="hidden md:flex gap-8">
              <a href="#features" className="text-[#5A5A5A] hover:text-[#E94B7B] transition">Features</a>
              <a href="#about" className="text-[#5A5A5A] hover:text-[#E94B7B] transition">About</a>
              <a href="#contact" className="text-[#5A5A5A] hover:text-[#E94B7B] transition">Contact</a>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="space-y-6">
            <h1 className="text-5xl md:text-6xl font-bold leading-tight">
              <span className="text-[#2D5B6E]">AI for Every Phase</span>
              <br />
              <span className="text-[#E94B7B]">of Her Health</span>
            </h1>
            <p className="text-lg text-[#666] leading-relaxed">
              Rhythma is an AI-powered women's health companion designed specifically for India. Track your menstrual cycle, get personalized insights, and access health guidance in your own language—all with complete privacy.
            </p>
            <div className="flex gap-4 pt-4">
              <button className="bg-[#E94B7B] text-white px-8 py-3 rounded-full font-semibold hover:bg-[#D63A6A] transition">
                Get Started
              </button>
              <button className="border-2 border-[#E94B7B] text-[#E94B7B] px-8 py-3 rounded-full font-semibold hover:bg-[#FFE8F0] transition">
                Learn More
              </button>
            </div>
            <div className="flex flex-wrap gap-6 pt-8">
              <a href="https://www.linkedin.com/company/130984014" target="_blank" rel="noopener noreferrer" className="text-[#666] hover:text-[#E94B7B] transition text-sm font-medium">
                LinkedIn
              </a>
              <a href="https://x.com/rhythmaAI" target="_blank" rel="noopener noreferrer" className="text-[#666] hover:text-[#E94B7B] transition text-sm font-medium">
                Twitter
              </a>
              <a href="https://l1nk.dev/elwevm5" target="_blank" rel="noopener noreferrer" className="text-[#666] hover:text-[#E94B7B] transition text-sm font-medium">
                Instagram
              </a>
              <a href="mailto:rhythma.official@gmail.com" className="text-[#666] hover:text-[#E94B7B] transition text-sm font-medium">
                Email
              </a>
            </div>
          </div>
          <div className="relative h-96 md:h-[500px]">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_8NWOzdsTB8KXKc0MgPabkA-YnCpKZ3GwZoeVEZxYfvyNa4a8DYJuH.webp"
              alt="Rhythma Dashboard showing menstrual cycle tracking with health metrics and AI insights"
              fill
              className="object-cover rounded-3xl shadow-2xl border-8 border-[#D4A547]/30"
            />
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold text-[#2D5B6E] mb-4">Powerful Features Built for You</h2>
          <p className="text-lg text-[#666]">Everything you need to understand your health better</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {[
            {
              icon: '📱',
              title: 'Smart Cycle Tracking',
              desc: 'Log periods, symptoms, and lifestyle factors. Get predictive insights about your cycle patterns.'
            },
            {
              icon: '🤖',
              title: 'AI Health Assistant',
              desc: 'Ask questions in Hindi, Marathi, Tamil, and more. Get personalized, educational health guidance.'
            },
            {
              icon: '❤️',
              title: 'Health Score',
              desc: 'Comprehensive wellness score combining cycle, sleep, stress, and lifestyle data.'
            },
            {
              icon: '📊',
              title: 'Variability Index',
              desc: 'Track cycle irregularities over 6-12 months and spot potential concerns early.'
            },
            {
              icon: '🔒',
              title: 'Privacy First',
              desc: 'AES-256 encryption. Your data stays on your device. You control everything.'
            },
            {
              icon: '📵',
              title: 'Works Offline',
              desc: 'Full functionality without internet. Sync seamlessly when connected.'
            }
          ].map((feature, idx) => (
            <div key={idx} className="bg-white p-8 rounded-2xl shadow-sm border border-[#E8DDD5] hover:shadow-lg transition duration-300">
              <div className="text-4xl mb-4">{feature.icon}</div>
              <h3 className="text-xl font-bold text-[#2D5B6E] mb-3">{feature.title}</h3>
              <p className="text-[#666] leading-relaxed">{feature.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* AI Assistant Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="relative h-96 md:h-[450px]">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_VTIclvoMd2xreJ7H3MeLng-eYaF564KJ4yfeIf2PGiepnJbBSjOCh.webp"
              alt="AI Assistant interface showing multilingual health guidance and symptom checking"
              fill
              className="object-cover rounded-3xl shadow-2xl border-8 border-[#6B3F7F]/20"
            />
          </div>
          <div className="space-y-6">
            <h2 className="text-4xl font-bold text-[#2D5B6E]">Powered by AI, Built for India</h2>
            <p className="text-lg text-[#666] leading-relaxed">
              Rhythma's conversational AI assistant uses Google Gemini to provide multilingual health guidance. Ask your questions in Hindi, Marathi, Tamil, or English—and get clear, compassionate answers.
            </p>
            <ul className="space-y-4">
              {[
                'Understands your symptoms in your language',
                'Provides educational health insights',
                'Respects cultural context and sensitivities',
                'Guides you toward professional care when needed'
              ].map((item, idx) => (
                <li key={idx} className="flex gap-3 items-start">
                  <span className="text-[#E94B7B] text-xl font-bold">✓</span>
                  <span className="text-[#666]">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Screenshots Grid */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <h2 className="text-4xl font-bold text-center text-[#2D5B6E] mb-16">See It In Action</h2>
        <div className="grid md:grid-cols-2 gap-8">
          <div className="rounded-2xl overflow-hidden shadow-lg border border-[#E8DDD5] h-80 relative">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_e__Q-NizgTu1-ej-hVOecg-2u16BjtOAgH8Wlb1tQLIgl5kDGoEsw.webp"
              alt="Health Insights showing cycle patterns and wellness recommendations"
              fill
              className="object-cover"
            />
          </div>
          <div className="rounded-2xl overflow-hidden shadow-lg border border-[#E8DDD5] h-80 relative">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_hPkeIoLtVGJRQGRZqCmrmw-trZv3cYvUdnYXpcBB4YYs7SlDcBPCR.webp"
              alt="Cycle Calendar with fertility window and phase tracking visualization"
              fill
              className="object-cover"
            />
          </div>
          <div className="rounded-2xl overflow-hidden shadow-lg border border-[#E8DDD5] h-80 relative">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_F3b3nYwlPTEYppjpDtV-0w-JvgAyGJczG3bgl1mBOmkv6zumGwH56.webp"
              alt="Menstrual Health Score dashboard with comprehensive component breakdown"
              fill
              className="object-cover"
            />
          </div>
          <div className="rounded-2xl overflow-hidden shadow-lg border border-[#E8DDD5] h-80 relative">
            <Image
              src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/Screenshot%202026-06-08%20150542-59Yr8TlHYgwXRXrHYVDbjV2PBXyeG1.png"
              alt="Cycle Variability Index showing 6-month pattern analysis"
              fill
              className="object-cover"
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
              <p className="text-lg leading-relaxed mb-6 text-[#E8DDD5]">
                For millions of women in India, conversations about menstrual health are surrounded by stigma and misinformation. Existing apps assume English fluency, stable internet, and global healthcare systems that don't reflect Indian reality.
              </p>
              <p className="text-lg leading-relaxed mb-6 text-[#E8DDD5]">
                Rhythma was built from the ground up for Indian women. We believe technology can shift the landscape of women's health by enabling earlier awareness, better health literacy, and stigma reduction.
              </p>
              <div className="space-y-3">
                <p className="flex items-center gap-2">
                  <span className="text-[#D4A547]">🌍</span> Available in Hindi, Marathi, Tamil, and more
                </p>
                <p className="flex items-center gap-2">
                  <span className="text-[#D4A547]">📵</span> Works fully offline with seamless sync
                </p>
                <p className="flex items-center gap-2">
                  <span className="text-[#D4A547]">💬</span> SMS support for low-data environments
                </p>
                <p className="flex items-center gap-2">
                  <span className="text-[#D4A547]">🔐</span> Privacy and security by default
                </p>
              </div>
            </div>
            <div className="flex justify-center h-80 relative">
              <Image
                src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/1_VquHjCKhk2vu-URzfWXezw-V5vHoGiq6MnTN6pAV5sGW8ikPTyDnk.webp"
                alt="Rhythma logo and branding - AI for Every Phase of Her Health"
                fill
                className="object-contain"
              />
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section id="contact" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="bg-gradient-to-r from-[#E94B7B] to-[#D63A6A] rounded-3xl p-12 text-center text-white">
          <h2 className="text-4xl font-bold mb-4">Ready to Take Control?</h2>
          <p className="text-xl mb-8 max-w-2xl mx-auto">
            Join thousands of women using Rhythma to better understand their health. Download the app or stay updated.
          </p>
          <form onSubmit={handleSubmit} className="flex gap-2 max-w-md mx-auto flex-col sm:flex-row">
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 px-6 py-3 rounded-full bg-white/90 text-[#2D5B6E] placeholder-[#999] focus:outline-none focus:ring-2 focus:ring-white"
              required
            />
            <button
              type="submit"
              className="bg-white text-[#E94B7B] px-8 py-3 rounded-full font-bold hover:bg-[#F0F0F0] transition whitespace-nowrap"
            >
              Subscribe
            </button>
          </form>
          {submitted && (
            <p className="mt-4 text-white animate-pulse">Thanks for subscribing! We'll be in touch soon. 💕</p>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#2D5B6E] text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <h3 className="font-bold text-lg mb-4">Rhythma</h3>
              <p className="text-[#B0D4E3]">AI for every phase of her health.</p>
            </div>
            <div>
              <h4 className="font-bold mb-4">Product</h4>
              <ul className="space-y-2 text-[#B0D4E3]">
                <li><a href="#features" className="hover:text-white transition">Features</a></li>
                <li><a href="#about" className="hover:text-white transition">About</a></li>
                <li><a href="#" className="hover:text-white transition">Blog</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold mb-4">Connect</h4>
              <ul className="space-y-2 text-[#B0D4E3]">
                <li><a href="https://x.com/rhythmaAI" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Twitter</a></li>
                <li><a href="https://www.linkedin.com/company/130984014" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">LinkedIn</a></li>
                <li><a href="https://l1nk.dev/elwevm5" target="_blank" rel="noopener noreferrer" className="hover:text-white transition">Instagram</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-bold mb-4">Contact</h4>
              <p className="text-[#B0D4E3]">
                <a href="mailto:rhythma.official@gmail.com" className="hover:text-white transition">
                  rhythma.official@gmail.com
                </a>
              </p>
            </div>
          </div>
          <div className="border-t border-[#4A7F9E] pt-8 text-center text-[#B0D4E3]">
            <p>&copy; 2026 Rhythma. All rights reserved. | Educational tool. Not a medical device.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
