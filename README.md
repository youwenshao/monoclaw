# MonoClaw

MonoClaw offers a service that sets up a virtual employee named **Mona**, powered by local LLMs running on dedicated Mac hardware in Hong Kong. Operated by **Sentimento Technologies Limited**, MonoClaw provides a tailored software suite over base OpenClaw, offering intuitive and seamless integration into existing business workflows with a focus on privacy and data integrity.

Product Website: [www.monoclaw.app](https://www.monoclaw.app)  
Powered by: [OpenClaw](https://www.openclaw.ai)

---

## 🚀 Overview

MonoClaw bridges the gap between advanced AI agents and local business needs. We provide a turn-key solution where clients purchase high-performance Mac hardware (Mac mini M4 or iMac M4), and we provision it with a hardened, pre-configured AI environment capable of running a variety of local LLMs.

### Key Features
- **Privacy First**: Local LLM deployment ensures sensitive data never leaves the client's hardware.
- **Tailored for HK**: Pre-loaded software stacks for 8 major Hong Kong industry verticals and 4 professional personas.
- **Trilingual Support**: Mona speaks and understands English, Traditional Chinese (Cantonese), and Simplified Chinese.
- **Zero Recurring Fees**: A flat software suite price with no monthly maintenance or subscription.
- **Plug-and-Play**: Devices are fully tested and provisioned at our office before being delivered to the client.

---

## 🏗️ Repository Structure

This monorepo contains the entire MonoClaw ecosystem:

```
monoclaw/
├── web/                  # Next.js 14 Frontend (Vercel)
│   ├── app/[locale]/     # Trilingual App Router (EN/TC/SC)
│   ├── components/       # shadcn/ui + Tailwind v4 components
│   ├── lib/              # Supabase, Stripe, and i18n utilities
│   └── messages/         # Translation JSON files
├── device-cli/           # Python Provisioning CLI
│   ├── openclaw_setup/   # Core logic for setup and self-destruct
│   └── test_suite/       # 80+ tests (Hardware, LLM, Security, etc.)
├── supabase/             # Database Layer
│   └── migrations/       # SQL schema for orders, devices, and tests
├── prompts/              # Coding Agent Prompts
│   └── [industry]/       # 48 prompts for industry-specific tools
└── .cursor/              # Project plans and rules
```

---

## 💻 Tech Stack

### Frontend & Dashboard
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS v4, shadcn/ui, Framer Motion
- **Internationalization**: `next-intl` (English, 繁體中文, 简体中文)
- **Backend/Auth**: Supabase (PostgreSQL, Auth, RLS). Google SSO setup and troubleshooting: [web/docs/AUTH_GOOGLE_SSO.md](web/docs/AUTH_GOOGLE_SSO.md)
- **Payments**: Stripe (HKD, Apple Pay, Credit Cards)

### Device Provisioning
- **Language**: Python 3.11+
- **LLM Framework**: MLX (Apple Silicon optimized)
- **Testing**: Custom framework with `rich` reporting
- **Security**: macOS `chflags` immutability, sandboxed execution

---

## 🛠️ Implementation Phases

1.  **Foundation**: Initialized Next.js scaffold, Supabase schema, and trilingual i18n skeleton.
2.  **Marketing Site**: Built the public-facing website, including interactive pricing and 12 industry detail pages.
3.  **Checkout Flow**: Implemented a 4-step order wizard with Stripe integration and automated order creation.
4.  **Dashboards**: Created client-side order tracking and device test report viewers, plus admin-side order management.
5.  **Device CLI**: Developed the `openclaw-setup` tool for hardware provisioning and comprehensive pre-shipping QA.
6.  **Agent Prompts**: Authored 48 detailed prompts for coding agents to implement the industry-specific productivity tools.

---

## 📦 Supported Local Models

Clients can select from a wide range of models optimized for 16GB RAM:
- **Fast (<2B)**: Qwen-3.5 0.8B, DeepSeek-R1 1.5B, Llama-3.1 1B, SmolLM2 1.7B, Gemma-3 1B
- **Standard (2-7B)**: DeepSeek-R1 7B, Llama-3.2 3B, Mistral 7B, Ministral 3B, Gemma-3 4B
- **Think (>7B)**: Qwen-3.5 9B, GLM-4 9B, Llama-3.1 8B, Ministral 8B
- **Coder**: Qwen-2.5-coder 7B, DeepSeek-coder 6.7B

---

## 🏢 Industry Verticals

We provide specialized software for:
- Real Estate & Property Agencies
- Immigration Consulting
- F&B & Hospitality
- Accounting & Bookkeeping
- Legal & Professional Services
- Medical & Dental Clinics
- Construction & Property Management
- Import/Export & Trading
- *Plus specialized profiles for Researchers, Developers, Solopreneurs, and Students.*

---

## ⚖️ Legal & Privacy

MonoClaw is a product of **Sentimento Technologies Limited**. All client data is treated as confidential under the Hong Kong Personal Data (Privacy) Ordinance (PDPO). Our software suite is sold as a one-time purchase with no recurring maintenance fees, as per the signed client contract.

---

© 2026 Sentimento Technologies Limited. Made in Hong Kong.
