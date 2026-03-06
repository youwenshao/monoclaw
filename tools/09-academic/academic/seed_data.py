"""Demo data seeder for the Academic Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.academic.seed")

# ---------------------------------------------------------------------------
# PaperSieve — sample paper metadata
# ---------------------------------------------------------------------------
SAMPLE_PAPERS = [
    {
        "title": "Deep Learning for Natural Language Processing: A Survey",
        "authors": json.dumps([{"family": "Wong", "given": "Tai Man", "name_tc": "黃大文"}, {"family": "Chen", "given": "Mei Ling", "name_tc": "陳美玲"}]),
        "abstract": "This survey provides a comprehensive overview of deep learning techniques applied to NLP tasks, covering architectures from RNNs to Transformers.",
        "doi": "10.1234/nlp.survey.2025",
        "year": 2025,
        "journal": "Journal of Artificial Intelligence Research",
        "volume": "48",
        "pages": "1-45",
        "language": "en",
        "tags": json.dumps(["NLP", "deep learning", "survey"]),
    },
    {
        "title": "基於大語言模型的中文學術文本摘要生成研究",
        "authors": json.dumps([{"family": "李", "given": "小明", "name_tc": "李小明"}, {"family": "張", "given": "偉", "name_tc": "張偉"}]),
        "abstract": "本文探討利用大語言模型進行中文學術文本自動摘要生成的方法，並在多個中文學術數據集上進行了實驗驗證。",
        "doi": "10.5678/chinese.llm.2025",
        "year": 2025,
        "journal": "計算機學報",
        "volume": "47",
        "pages": "2301-2315",
        "language": "tc",
        "tags": json.dumps(["LLM", "中文NLP", "摘要生成"]),
    },
    {
        "title": "Federated Learning for Privacy-Preserving Healthcare AI in Hong Kong",
        "authors": json.dumps([{"family": "Lam", "given": "Ka Wai", "name_tc": "林嘉偉"}, {"family": "Yip", "given": "Siu Fung", "name_tc": "葉兆豐"}, {"family": "Ng", "given": "Wing Yin", "name_tc": "吳詠賢"}]),
        "abstract": "We propose a federated learning framework enabling collaborative model training across Hong Kong hospitals without sharing patient data.",
        "doi": "10.9012/fl.healthcare.2024",
        "year": 2024,
        "journal": "IEEE Transactions on Medical Imaging",
        "volume": "43",
        "pages": "890-905",
        "language": "en",
        "tags": json.dumps(["federated learning", "healthcare", "privacy"]),
    },
    {
        "title": "Cross-Lingual Transfer Learning for Low-Resource Cantonese NLP",
        "authors": json.dumps([{"family": "Chan", "given": "Ho Yin", "name_tc": "陳浩然"}, {"family": "Wong", "given": "Tai Man", "name_tc": "黃大文"}]),
        "abstract": "This paper investigates cross-lingual transfer techniques to improve NLP performance for Cantonese, a low-resource language despite millions of speakers.",
        "doi": "10.3456/cantonese.nlp.2025",
        "year": 2025,
        "journal": "Proceedings of ACL 2025",
        "volume": None,
        "pages": "3421-3436",
        "language": "en",
        "tags": json.dumps(["Cantonese", "NLP", "transfer learning"]),
    },
    {
        "title": "Quantum Computing Algorithms for Combinatorial Optimization",
        "authors": json.dumps([{"family": "Liu", "given": "Wei", "name_tc": "劉偉"}, {"family": "Zhang", "given": "Xin", "name_tc": "張欣"}]),
        "abstract": "We review recent advances in quantum computing algorithms for solving combinatorial optimization problems with near-term quantum devices.",
        "doi": "10.7890/quantum.opt.2024",
        "year": 2024,
        "journal": "Nature Reviews Physics",
        "volume": "6",
        "pages": "120-138",
        "language": "en",
        "tags": json.dumps(["quantum computing", "optimization", "review"]),
    },
    {
        "title": "香港高等教育國際化的挑戰與機遇",
        "authors": json.dumps([{"family": "何", "given": "家強", "name_tc": "何家強"}]),
        "abstract": "本文分析了香港八所大學資助委員會資助大學在國際化進程中面臨的挑戰和策略。",
        "doi": "10.2345/hk.edu.intl.2025",
        "year": 2025,
        "journal": "高等教育研究",
        "volume": "46",
        "pages": "78-92",
        "language": "tc",
        "tags": json.dumps(["higher education", "internationalization", "Hong Kong"]),
    },
]

# ---------------------------------------------------------------------------
# CiteBot — sample citations
# ---------------------------------------------------------------------------
SAMPLE_CITATIONS = [
    {
        "doi": "10.1038/s41586-023-06747-5",
        "title": "GPT-4 Technical Report",
        "authors": json.dumps([{"family": "OpenAI", "given": ""}]),
        "year": 2023,
        "journal": "arXiv preprint",
        "entry_type": "article",
        "language": "en",
        "verified": True,
    },
    {
        "doi": "10.1145/3442188.3445922",
        "title": "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?",
        "authors": json.dumps([{"family": "Bender", "given": "Emily M."}, {"family": "Gebru", "given": "Timnit"}, {"family": "McMillan-Major", "given": "Angelina"}, {"family": "Shmitchell", "given": "Shmargaret"}]),
        "year": 2021,
        "journal": "Proceedings of FAccT",
        "entry_type": "conference",
        "language": "en",
        "verified": True,
    },
    {
        "doi": "10.1016/j.artint.2024.104123",
        "title": "A Survey of Large Language Models",
        "authors": json.dumps([{"family": "Zhao", "given": "Wayne Xin"}, {"family": "Zhou", "given": "Kun"}, {"family": "Li", "given": "Junyi"}]),
        "year": 2024,
        "journal": "Artificial Intelligence",
        "volume": "330",
        "entry_type": "article",
        "language": "en",
        "verified": True,
    },
    {
        "doi": None,
        "title": "深度學習在中醫藥研究中的應用綜述",
        "authors": json.dumps([{"family": "王", "given": "小華", "name_tc": "王小華"}, {"family": "趙", "given": "明", "name_tc": "趙明"}]),
        "year": 2024,
        "journal": "中國中藥雜誌",
        "volume": "49",
        "pages": "1234-1250",
        "entry_type": "article",
        "language": "tc",
        "verified": False,
    },
    {
        "doi": "10.1007/978-3-030-72113-8_1",
        "title": "Attention Is All You Need",
        "authors": json.dumps([{"family": "Vaswani", "given": "Ashish"}, {"family": "Shazeer", "given": "Noam"}, {"family": "Parmar", "given": "Niki"}]),
        "year": 2017,
        "journal": "Advances in Neural Information Processing Systems",
        "volume": "30",
        "entry_type": "conference",
        "language": "en",
        "verified": True,
    },
    {
        "doi": "10.1126/science.aax2342",
        "title": "The Ethics of Artificial Intelligence in Education",
        "authors": json.dumps([{"family": "Holmes", "given": "Wayne"}, {"family": "Bialik", "given": "Maya"}, {"family": "Fadel", "given": "Charles"}]),
        "year": 2023,
        "journal": "Science",
        "volume": "382",
        "pages": "42-48",
        "entry_type": "article",
        "language": "en",
        "verified": True,
    },
    {
        "doi": None,
        "title": "Research Methods in Applied Linguistics",
        "authors": json.dumps([{"family": "Dörnyei", "given": "Zoltán"}]),
        "year": 2007,
        "journal": None,
        "publisher": "Oxford University Press",
        "entry_type": "book",
        "language": "en",
        "verified": True,
    },
    {
        "doi": "10.1080/13603116.2023.2190218",
        "title": "Inclusive Education in Hong Kong: Policy and Practice",
        "authors": json.dumps([{"family": "Forlin", "given": "Chris"}, {"family": "Sin", "given": "Kuen Fung", "name_tc": "冼權鋒"}]),
        "year": 2023,
        "journal": "International Journal of Inclusive Education",
        "volume": "27",
        "issue": "8",
        "pages": "912-930",
        "entry_type": "article",
        "language": "en",
        "verified": True,
    },
]

SAMPLE_BIB_PROJECTS = [
    {"project_name": "PhD Thesis Bibliography", "default_style": "apa7", "description": "References for doctoral dissertation"},
    {"project_name": "JAIR Submission 2026", "default_style": "apa7", "description": "Journal of AI Research paper"},
    {"project_name": "IEEE Conference Paper", "default_style": "ieee", "description": "Conference submission"},
]

# ---------------------------------------------------------------------------
# TranslateAssist — sample translation projects and glossary
# ---------------------------------------------------------------------------
SAMPLE_TRANSLATION_PROJECTS = [
    {
        "project_name": "NLP Survey Abstract — EN→TC",
        "source_language": "en",
        "target_language": "tc",
        "domain": "stem",
        "status": "in_progress",
    },
    {
        "project_name": "教育研究摘要 — TC→EN",
        "source_language": "tc",
        "target_language": "en",
        "domain": "social_science",
        "status": "in_progress",
    },
]

SAMPLE_SEGMENTS = [
    {
        "project_idx": 0,
        "segment_index": 0,
        "section_name": "Abstract",
        "source_text": "This survey provides a comprehensive overview of deep learning techniques applied to natural language processing tasks.",
        "translated_text": "本綜述全面概述了深度學習技術在自然語言處理任務中的應用。",
        "review_status": "reviewed",
        "confidence": 0.92,
    },
    {
        "project_idx": 0,
        "segment_index": 1,
        "section_name": "Abstract",
        "source_text": "We cover architectures from recurrent neural networks to Transformer models and discuss their effectiveness across various NLP benchmarks.",
        "translated_text": "我們涵蓋了從循環神經網絡到Transformer模型的架構，並討論了它們在各種自然語言處理基準測試中的有效性。",
        "review_status": "auto",
        "confidence": 0.88,
    },
    {
        "project_idx": 1,
        "segment_index": 0,
        "section_name": "摘要",
        "source_text": "本文分析了香港八所大學資助委員會資助大學在國際化進程中面臨的挑戰和策略。",
        "translated_text": "This paper analyses the challenges and strategies faced by the eight UGC-funded universities in Hong Kong in their internationalisation process.",
        "review_status": "approved",
        "confidence": 0.95,
    },
]

SAMPLE_GLOSSARY = [
    {"term_en": "natural language processing", "term_tc": "自然語言處理", "term_sc": "自然语言处理", "domain": "stem"},
    {"term_en": "deep learning", "term_tc": "深度學習", "term_sc": "深度学习", "domain": "stem"},
    {"term_en": "Transformer", "term_tc": "Transformer", "term_sc": "Transformer", "domain": "stem"},
    {"term_en": "federated learning", "term_tc": "聯邦學習", "term_sc": "联邦学习", "domain": "stem"},
    {"term_en": "University Grants Committee", "term_tc": "大學教育資助委員會", "term_sc": "大学教育资助委员会", "domain": "social_science"},
    {"term_en": "Research Grants Council", "term_tc": "研究資助局", "term_sc": "研究资助局", "domain": "general"},
    {"term_en": "inclusive education", "term_tc": "融合教育", "term_sc": "融合教育", "domain": "social_science"},
    {"term_en": "principal investigator", "term_tc": "首席研究員", "term_sc": "首席研究员", "domain": "general"},
]

# ---------------------------------------------------------------------------
# GrantTracker — schemes, deadlines, researcher, applications, publications
# ---------------------------------------------------------------------------
SAMPLE_RESEARCHER = {
    "name_en": "Dr. Wong Tai Man",
    "name_tc": "黃大文",
    "title": "Associate Professor",
    "department": "Department of Computer Science",
    "institution": "The University of Hong Kong",
    "email": "tmwong@cs.hku.hk",
    "orcid": "0000-0001-2345-6789",
    "google_scholar_id": "ABC123DEF",
    "research_interests": "Natural Language Processing, Machine Learning, Computational Linguistics",
    "appointment_date": "2018-09-01",
}

SAMPLE_GRANT_SCHEMES = [
    {"agency": "RGC", "scheme_name": "General Research Fund", "scheme_code": "GRF", "description": "Main competitive research funding scheme for academic research in HK", "typical_deadline_month": 11, "typical_funding_range": "HK$500,000 - HK$1,500,000", "duration_years": 2, "eligibility_notes": "All UGC-funded university academics", "url": "https://www.ugc.edu.hk/eng/rgc/funding/grf.html"},
    {"agency": "RGC", "scheme_name": "Early Career Scheme", "scheme_code": "ECS", "description": "For junior researchers within 3 years of first academic appointment", "typical_deadline_month": 11, "typical_funding_range": "HK$500,000 - HK$1,200,000", "duration_years": 2, "eligibility_notes": "Within 3 years of first appointment", "url": "https://www.ugc.edu.hk/eng/rgc/funding/ecs.html"},
    {"agency": "RGC", "scheme_name": "Collaborative Research Fund", "scheme_code": "CRF", "description": "Group research projects involving multiple PIs", "typical_deadline_month": 3, "typical_funding_range": "HK$2,000,000 - HK$8,000,000", "duration_years": 3, "eligibility_notes": "Minimum 3 PIs from 2+ institutions", "url": "https://www.ugc.edu.hk/eng/rgc/funding/crf.html"},
    {"agency": "RGC", "scheme_name": "Theme-based Research Scheme", "scheme_code": "TRS", "description": "Large strategic research projects on themes of strategic importance", "typical_deadline_month": 6, "typical_funding_range": "HK$25,000,000 - HK$75,000,000", "duration_years": 5, "eligibility_notes": "By invitation or open call", "url": "https://www.ugc.edu.hk/eng/rgc/funding/trs.html"},
    {"agency": "RGC", "scheme_name": "Research Impact Fund", "scheme_code": "RIF", "description": "Impact-oriented research with demonstrable societal benefit", "typical_deadline_month": 4, "typical_funding_range": "HK$2,500,000 - HK$10,000,000", "duration_years": 3, "eligibility_notes": "Must demonstrate research impact pathway", "url": "https://www.ugc.edu.hk/eng/rgc/funding/rif.html"},
    {"agency": "RGC", "scheme_name": "Hong Kong PhD Fellowship Scheme", "scheme_code": "HKPFS", "description": "Prestigious doctoral fellowships for outstanding students", "typical_deadline_month": 12, "typical_funding_range": "HK$331,200/year stipend + conference/research travel", "duration_years": 4, "eligibility_notes": "Outstanding PhD applicants worldwide", "url": "https://www.ugc.edu.hk/eng/rgc/funding/hkpfs.html"},
    {"agency": "ITF", "scheme_name": "Innovation and Technology Support Programme", "scheme_code": "ITSP", "description": "R&D projects in applied technology", "typical_deadline_month": None, "typical_funding_range": "Up to HK$10,000,000", "duration_years": 2, "eligibility_notes": "Universities and R&D centres", "url": "https://www.itf.gov.hk/en/funding-programmes/itsp/"},
    {"agency": "NSFC", "scheme_name": "NSFC General Program", "scheme_code": "NSFC-GP", "description": "National Natural Science Foundation general program", "typical_deadline_month": 3, "typical_funding_range": "RMB 500,000 - RMB 800,000", "duration_years": 4, "eligibility_notes": "Must have Mainland collaborator for HK applicants", "url": "https://www.nsfc.gov.cn/english/"},
    {"agency": "NSFC", "scheme_name": "NSFC/RGC Joint Research Scheme", "scheme_code": "NSFC-RGC", "description": "Joint scheme for HK-Mainland collaborative research", "typical_deadline_month": 3, "typical_funding_range": "HK$1,250,000 + RMB 1,000,000", "duration_years": 4, "eligibility_notes": "Joint HK-Mainland PI pairs", "url": "https://www.ugc.edu.hk/eng/rgc/funding/nsfc.html"},
]

SAMPLE_DEADLINES = [
    {"scheme_idx": 0, "year": 2026, "external_deadline": "2026-11-15", "institutional_deadline": "2026-10-25", "status": "upcoming"},
    {"scheme_idx": 1, "year": 2026, "external_deadline": "2026-11-15", "institutional_deadline": "2026-10-25", "status": "upcoming"},
    {"scheme_idx": 2, "year": 2026, "external_deadline": "2026-03-31", "institutional_deadline": "2026-03-10", "status": "open"},
    {"scheme_idx": 4, "year": 2026, "external_deadline": "2026-04-30", "institutional_deadline": "2026-04-09", "status": "upcoming"},
    {"scheme_idx": 7, "year": 2026, "external_deadline": "2026-03-20", "institutional_deadline": "2026-02-27", "status": "open"},
    {"scheme_idx": 8, "year": 2026, "external_deadline": "2026-03-20", "institutional_deadline": "2026-02-27", "status": "open"},
]

SAMPLE_APPLICATIONS = [
    {
        "scheme_idx": 0,
        "deadline_idx": 0,
        "project_title": "Cross-Lingual Transfer Learning for Low-Resource Asian Languages",
        "requested_amount": 1200000,
        "duration_months": 24,
        "status": "drafting",
    },
    {
        "scheme_idx": 2,
        "deadline_idx": 2,
        "project_title": "Collaborative AI Framework for Multilingual Healthcare NLP",
        "requested_amount": 4500000,
        "duration_months": 36,
        "status": "planning",
    },
    {
        "scheme_idx": 8,
        "deadline_idx": 5,
        "project_title": "Joint Research on Chinese Medical Text Understanding",
        "requested_amount": 1250000,
        "duration_months": 48,
        "status": "submitted",
        "submission_date": "2026-02-25",
    },
]

SAMPLE_PUBLICATIONS = [
    {"title": "Deep Learning for Natural Language Processing: A Survey", "authors": "Wong, T.M., Chen, M.L.", "journal": "Journal of Artificial Intelligence Research", "year": 2025, "doi": "10.1234/nlp.survey.2025", "citation_count": 12, "is_corresponding_author": True},
    {"title": "Cross-Lingual Transfer Learning for Low-Resource Cantonese NLP", "authors": "Chan, H.Y., Wong, T.M.", "journal": "Proceedings of ACL 2025", "year": 2025, "doi": "10.3456/cantonese.nlp.2025", "citation_count": 5, "is_corresponding_author": True},
    {"title": "Federated Learning for Privacy-Preserving Healthcare AI", "authors": "Lam, K.W., Yip, S.F., Ng, W.Y.", "journal": "IEEE Trans. Medical Imaging", "year": 2024, "doi": "10.9012/fl.healthcare.2024", "citation_count": 28, "is_corresponding_author": False},
    {"title": "Bilingual Sentiment Analysis with Code-Switching Detection", "authors": "Wong, T.M., Lee, J.S.", "journal": "Computational Linguistics", "year": 2024, "doi": "10.1162/coli.2024.0042", "citation_count": 8, "is_corresponding_author": True},
    {"title": "Efficient Fine-Tuning of Large Language Models for Domain Adaptation", "authors": "Wong, T.M., Zhang, X.", "journal": "Proceedings of EMNLP 2023", "year": 2023, "doi": "10.18653/v1/2023.emnlp-main.542", "citation_count": 35, "is_corresponding_author": True},
]

SAMPLE_BUDGET_ITEMS = [
    {"app_idx": 0, "category": "ra_salary", "description": "Research Assistant (full-time, 24 months)", "year": 1, "amount": 432000, "justification": "Full-time RA at HK$18,000/month for data collection and experiments"},
    {"app_idx": 0, "category": "equipment", "description": "GPU Workstation (NVIDIA A100)", "year": 1, "amount": 180000, "justification": "Required for training multilingual NLP models"},
    {"app_idx": 0, "category": "travel", "description": "Conference attendance (ACL/EMNLP)", "year": 1, "amount": 40000, "justification": "Present research findings at top NLP venue"},
    {"app_idx": 0, "category": "travel", "description": "Conference attendance", "year": 2, "amount": 40000, "justification": "Second year conference participation"},
    {"app_idx": 0, "category": "consumables", "description": "Cloud computing credits (backup)", "year": 1, "amount": 50000, "justification": "AWS/GCP credits for large-scale experiments"},
    {"app_idx": 0, "category": "consumables", "description": "Cloud computing credits", "year": 2, "amount": 50000, "justification": "Continued computation needs"},
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_paper_sieve(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        if existing > 0:
            logger.info("PaperSieve already has data, skipping seed")
            return 0

        for p in SAMPLE_PAPERS:
            conn.execute(
                """INSERT INTO papers
                   (title, authors, abstract, doi, year, journal, volume, pages, language, tags)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (p["title"], p["authors"], p["abstract"], p["doi"], p["year"],
                 p["journal"], p["volume"], p["pages"], p["language"], p["tags"]),
            )
            count += 1

    logger.info("Seeded %d PaperSieve records", count)
    return count


def seed_cite_bot(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
        if existing > 0:
            logger.info("CiteBot already has data, skipping seed")
            return 0

        for c in SAMPLE_CITATIONS:
            conn.execute(
                """INSERT INTO citations
                   (doi, title, authors, year, journal, volume, issue, pages, publisher,
                    language, entry_type, verified)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c.get("doi"), c["title"], c["authors"], c["year"],
                 c.get("journal"), c.get("volume"), c.get("issue"), c.get("pages"),
                 c.get("publisher"), c.get("language", "en"),
                 c.get("entry_type", "article"), c.get("verified", False)),
            )
            count += 1

        for bp in SAMPLE_BIB_PROJECTS:
            conn.execute(
                "INSERT INTO bibliography_projects (project_name, default_style, description) VALUES (?,?,?)",
                (bp["project_name"], bp["default_style"], bp["description"]),
            )
            count += 1

        project_ids = [r[0] for r in conn.execute("SELECT id FROM bibliography_projects ORDER BY id").fetchall()]
        citation_ids = [r[0] for r in conn.execute("SELECT id FROM citations ORDER BY id").fetchall()]
        for i, cid in enumerate(citation_ids[:5]):
            conn.execute(
                "INSERT INTO project_citations (project_id, citation_id, sort_order) VALUES (?,?,?)",
                (project_ids[0], cid, i + 1),
            )
            count += 1

    logger.info("Seeded %d CiteBot records", count)
    return count


def seed_translate_assist(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM translation_projects").fetchone()[0]
        if existing > 0:
            logger.info("TranslateAssist already has data, skipping seed")
            return 0

        for tp in SAMPLE_TRANSLATION_PROJECTS:
            conn.execute(
                """INSERT INTO translation_projects
                   (project_name, source_language, target_language, domain, status)
                   VALUES (?,?,?,?,?)""",
                (tp["project_name"], tp["source_language"], tp["target_language"],
                 tp["domain"], tp["status"]),
            )
            count += 1

        project_ids = [r[0] for r in conn.execute("SELECT id FROM translation_projects ORDER BY id").fetchall()]

        for seg in SAMPLE_SEGMENTS:
            pid = project_ids[seg["project_idx"]]
            conn.execute(
                """INSERT INTO translation_segments
                   (project_id, segment_index, section_name, source_text, translated_text,
                    review_status, confidence)
                   VALUES (?,?,?,?,?,?,?)""",
                (pid, seg["segment_index"], seg["section_name"], seg["source_text"],
                 seg["translated_text"], seg["review_status"], seg["confidence"]),
            )
            count += 1

        for g in SAMPLE_GLOSSARY:
            conn.execute(
                """INSERT INTO glossary_terms
                   (term_en, term_tc, term_sc, domain, project_specific)
                   VALUES (?,?,?,?,0)""",
                (g["term_en"], g["term_tc"], g["term_sc"], g["domain"]),
            )
            count += 1

    logger.info("Seeded %d TranslateAssist records", count)
    return count


def seed_grant_tracker(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM grant_schemes").fetchone()[0]
        if existing > 0:
            logger.info("GrantTracker already has data, skipping seed")
            return 0

        r = SAMPLE_RESEARCHER
        conn.execute(
            """INSERT INTO researchers
               (name_en, name_tc, title, department, institution, email, orcid,
                google_scholar_id, research_interests, appointment_date)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (r["name_en"], r["name_tc"], r["title"], r["department"], r["institution"],
             r["email"], r["orcid"], r["google_scholar_id"], r["research_interests"],
             r["appointment_date"]),
        )
        researcher_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        count += 1

        scheme_ids = []
        for gs in SAMPLE_GRANT_SCHEMES:
            conn.execute(
                """INSERT INTO grant_schemes
                   (agency, scheme_name, scheme_code, description, typical_deadline_month,
                    typical_funding_range, duration_years, eligibility_notes, url)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (gs["agency"], gs["scheme_name"], gs["scheme_code"], gs["description"],
                 gs["typical_deadline_month"], gs["typical_funding_range"],
                 gs["duration_years"], gs["eligibility_notes"], gs["url"]),
            )
            scheme_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        deadline_ids = []
        for dl in SAMPLE_DEADLINES:
            sid = scheme_ids[dl["scheme_idx"]]
            conn.execute(
                """INSERT INTO deadlines
                   (scheme_id, year, external_deadline, institutional_deadline, status)
                   VALUES (?,?,?,?,?)""",
                (sid, dl["year"], dl["external_deadline"],
                 dl["institutional_deadline"], dl["status"]),
            )
            deadline_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        app_ids = []
        for ap in SAMPLE_APPLICATIONS:
            sid = scheme_ids[ap["scheme_idx"]]
            did = deadline_ids[ap["deadline_idx"]]
            conn.execute(
                """INSERT INTO applications
                   (researcher_id, scheme_id, deadline_id, project_title, requested_amount,
                    duration_months, status, submission_date)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (researcher_id, sid, did, ap["project_title"], ap["requested_amount"],
                 ap["duration_months"], ap["status"], ap.get("submission_date")),
            )
            app_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for pub in SAMPLE_PUBLICATIONS:
            conn.execute(
                """INSERT INTO publications
                   (researcher_id, title, authors, journal, year, doi, citation_count,
                    is_corresponding_author)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (researcher_id, pub["title"], pub["authors"], pub["journal"],
                 pub["year"], pub["doi"], pub["citation_count"],
                 pub["is_corresponding_author"]),
            )
            count += 1

        for bi in SAMPLE_BUDGET_ITEMS:
            aid = app_ids[bi["app_idx"]]
            conn.execute(
                """INSERT INTO budget_items
                   (application_id, category, description, year, amount, justification)
                   VALUES (?,?,?,?,?,?)""",
                (aid, bi["category"], bi["description"], bi["year"],
                 bi["amount"], bi["justification"]),
            )
            count += 1

    logger.info("Seeded %d GrantTracker records", count)
    return count


def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "paper_sieve": seed_paper_sieve(db_paths["paper_sieve"]),
        "cite_bot": seed_cite_bot(db_paths["cite_bot"]),
        "translate_assist": seed_translate_assist(db_paths["translate_assist"]),
        "grant_tracker": seed_grant_tracker(db_paths["grant_tracker"]),
    }
