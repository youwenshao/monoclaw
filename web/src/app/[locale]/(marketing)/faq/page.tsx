import { setRequestLocale } from "next-intl/server";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

const FAQ_ITEMS = [
  {
    question: "What is MonoClaw?",
    answer:
      "MonoClaw is a service by Sentimento Technologies that deploys an AI-powered virtual employee named Mona on dedicated Mac hardware running locally in Hong Kong.",
  },
  {
    question: "What hardware do I need?",
    answer:
      "Choose between Mac mini M4 (~HK$5,000) or iMac M4 (~HK$10,000). Both come with Apple M4 chip and 16GB RAM. You purchase directly from Apple.",
  },
  {
    question: "How does the setup process work?",
    answer:
      "After payment, you purchase hardware from Apple and ship it to our office. We install OpenClaw with all 12 tool suites, run comprehensive tests, and deliver it ready to use.",
  },
  {
    question: "Are there any recurring fees?",
    answer:
      "No. The HK$39,999 software fee is a one-time payment. There are no monthly subscriptions or maintenance fees.",
  },
  {
    question: "What are local LLMs?",
    answer:
      "Local Large Language Models run entirely on your Mac hardware. Unlike cloud APIs, your data never leaves your device, ensuring complete privacy.",
  },
  {
    question: "Which LLM should I choose?",
    answer:
      "Start with the Pro Bundle (HK$999) for most users. It includes Fast, Think, and Coder models. The Max Bundle (HK$1,999) adds Standard models and automated routing.",
  },
  {
    question: "Can Mona speak Cantonese?",
    answer:
      "Yes! Mona supports English, Traditional Chinese, and Simplified Chinese through local voice synthesis and speech recognition.",
  },
  {
    question: "Is my data private?",
    answer:
      "Absolutely. All processing happens locally on your Mac. No data is sent to external servers unless you explicitly choose to use API-based models.",
  },
  {
    question: "What industries do you support?",
    answer:
      "We offer pre-loaded software for Real Estate, Immigration, F&B, Accounting, Legal, Medical/Dental, Construction, and Import/Export. We also serve researchers, developers, solopreneurs, and students.",
  },
  {
    question: "What if I need custom software?",
    answer:
      "Your OpenClaw agent can pull additional software from our GitHub repository at www.openclaw.ai. Contact us for bespoke development.",
  },
];

export default async function FaqPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mb-16 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Frequently Asked Questions
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          Everything you need to know about MonoClaw and your AI employee Mona.
        </p>
      </div>

      <Accordion type="single" collapsible className="w-full">
        {FAQ_ITEMS.map((item, index) => (
          <AccordionItem key={index} value={`item-${index}`}>
            <AccordionTrigger className="text-left text-base">
              {item.question}
            </AccordionTrigger>
            <AccordionContent className="text-muted-foreground">
              {item.answer}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
