"""Demo data seeder for the Solopreneur Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.solopreneur.seed")

# ---------------------------------------------------------------------------
# BizOwner OS sample data
# ---------------------------------------------------------------------------

SAMPLE_CUSTOMERS = [
    {"phone": "+85291234567", "name": "David Chan", "name_tc": "陳大文", "tags": '["regular","vip"]', "total_spend": 15800, "visit_count": 12},
    {"phone": "+85298765432", "name": "Wong Siu Ming", "name_tc": "黃小明", "tags": '["regular"]', "total_spend": 8200, "visit_count": 6},
    {"phone": "+85261234567", "name": "Li Mei Ling", "name_tc": "李美玲", "tags": '["new"]', "total_spend": 1200, "visit_count": 2},
    {"phone": "+85295551234", "name": "Sarah Chen", "name_tc": "陳莎拉", "tags": '["wholesale"]', "total_spend": 42000, "visit_count": 18},
    {"phone": "+85268887777", "name": "Ho Ka Keung", "name_tc": "何家強", "tags": '["corporate"]', "total_spend": 28500, "visit_count": 9},
]

SAMPLE_SALES = [
    {"total_amount": 380, "payment_method": "octopus", "items": '[{"name":"Milk Tea Set","qty":2,"price":68},{"name":"Pineapple Bun","qty":4,"price":18}]', "customer_phone": "+85291234567", "pos_source": "ichef", "days_ago": 0},
    {"total_amount": 156, "payment_method": "fps", "items": '[{"name":"Egg Tart","qty":6,"price":12},{"name":"Coffee","qty":2,"price":42}]', "customer_phone": "+85298765432", "pos_source": "ichef", "days_ago": 0},
    {"total_amount": 520, "payment_method": "credit_card", "items": '[{"name":"Set Lunch A","qty":2,"price":88},{"name":"Set Lunch B","qty":3,"price":98}]', "customer_phone": None, "pos_source": "ichef", "days_ago": 0},
    {"total_amount": 1280, "payment_method": "cash", "items": '[{"name":"Catering Package","qty":1,"price":1280}]', "customer_phone": "+85295551234", "pos_source": "manual", "days_ago": 1},
    {"total_amount": 245, "payment_method": "octopus", "items": '[{"name":"Milk Tea","qty":5,"price":32},{"name":"Toast","qty":3,"price":25}]', "customer_phone": None, "pos_source": "ichef", "days_ago": 1},
    {"total_amount": 680, "payment_method": "fps", "items": '[{"name":"Birthday Cake","qty":1,"price":680}]', "customer_phone": "+85268887777", "pos_source": "manual", "days_ago": 2},
    {"total_amount": 890, "payment_method": "credit_card", "items": '[{"name":"Set Dinner","qty":4,"price":168},{"name":"Drinks","qty":4,"price":55}]', "customer_phone": "+85291234567", "pos_source": "ichef", "days_ago": 2},
    {"total_amount": 350, "payment_method": "wechat_pay", "items": '[{"name":"Takeaway Lunch","qty":5,"price":70}]', "customer_phone": None, "pos_source": "ichef", "days_ago": 3},
    {"total_amount": 1560, "payment_method": "cash", "items": '[{"name":"Monthly Catering","qty":1,"price":1560}]', "customer_phone": "+85295551234", "pos_source": "manual", "days_ago": 5},
    {"total_amount": 420, "payment_method": "alipay", "items": '[{"name":"Afternoon Tea Set","qty":3,"price":140}]', "customer_phone": None, "pos_source": "ichef", "days_ago": 7},
]

SAMPLE_EXPENSES = [
    {"category": "rent", "description": "Monthly rent — Shop Unit B2, Central Market", "amount": 35000, "payment_method": "bank_transfer", "recurring": True, "days_ago": 1},
    {"category": "salary", "description": "Staff salaries (3 employees)", "amount": 48000, "payment_method": "bank_transfer", "recurring": True, "days_ago": 1},
    {"category": "inventory", "description": "Coffee beans — 10kg from Roast & Co", "amount": 2800, "payment_method": "fps", "recurring": False, "days_ago": 2},
    {"category": "utilities", "description": "CLP electricity bill", "amount": 3200, "payment_method": "bank_transfer", "recurring": True, "days_ago": 5},
    {"category": "inventory", "description": "Flour, sugar, butter from Wellcome wholesale", "amount": 1850, "payment_method": "cash", "recurring": False, "days_ago": 3},
    {"category": "marketing", "description": "Instagram sponsored post — CNY promotion", "amount": 500, "payment_method": "credit_card", "recurring": False, "days_ago": 8},
    {"category": "mpf", "description": "MPF contribution — January 2026", "amount": 4500, "payment_method": "bank_transfer", "recurring": True, "days_ago": 10},
    {"category": "equipment", "description": "New blender — Vitamix", "amount": 4800, "payment_method": "credit_card", "recurring": False, "days_ago": 15},
    {"category": "insurance", "description": "Shop insurance renewal — Zurich", "amount": 8500, "payment_method": "bank_transfer", "recurring": True, "days_ago": 20},
]

SAMPLE_INVENTORY = [
    {"item_name": "Coffee Beans (kg)", "item_name_tc": "咖啡豆 (公斤)", "current_stock": 8, "low_stock_threshold": 5, "unit_cost": 280},
    {"item_name": "Milk Tea Powder (kg)", "item_name_tc": "奶茶粉 (公斤)", "current_stock": 3, "low_stock_threshold": 5, "unit_cost": 120},
    {"item_name": "Evaporated Milk (can)", "item_name_tc": "淡奶 (罐)", "current_stock": 24, "low_stock_threshold": 12, "unit_cost": 15},
    {"item_name": "Flour (kg)", "item_name_tc": "麵粉 (公斤)", "current_stock": 2, "low_stock_threshold": 10, "unit_cost": 18},
    {"item_name": "Sugar (kg)", "item_name_tc": "糖 (公斤)", "current_stock": 15, "low_stock_threshold": 5, "unit_cost": 12},
    {"item_name": "Butter (block)", "item_name_tc": "牛油 (塊)", "current_stock": 6, "low_stock_threshold": 4, "unit_cost": 45},
    {"item_name": "Paper Cups (pack)", "item_name_tc": "紙杯 (包)", "current_stock": 4, "low_stock_threshold": 10, "unit_cost": 35},
    {"item_name": "Takeaway Boxes (pack)", "item_name_tc": "外賣盒 (包)", "current_stock": 8, "low_stock_threshold": 5, "unit_cost": 28},
]

SAMPLE_MESSAGES = [
    {"phone": "+85291234567", "direction": "inbound", "message_text": "Hi, what time do you close today?", "message_type": "text", "tags": '["hours"]', "requires_followup": False, "hours_ago": 2},
    {"phone": "+85298765432", "direction": "inbound", "message_text": "Can I order 10 egg tarts for pickup tomorrow?", "message_type": "text", "tags": '["order"]', "requires_followup": True, "hours_ago": 3},
    {"phone": "+85291234567", "direction": "outbound", "message_text": "We close at 10pm today! 今日營業至晚上10點！", "message_type": "text", "tags": '["auto_reply"]', "requires_followup": False, "hours_ago": 2},
    {"phone": "+85261234567", "direction": "inbound", "message_text": "Do you have gluten-free options?", "message_type": "text", "tags": '["menu"]', "requires_followup": True, "hours_ago": 5},
    {"phone": "+85268887777", "direction": "inbound", "message_text": "我想訂一個生日蛋糕，下星期六取", "message_type": "text", "tags": '["order","cake"]', "requires_followup": True, "hours_ago": 8},
]

# ---------------------------------------------------------------------------
# MPFCalc sample data
# ---------------------------------------------------------------------------

SAMPLE_EMPLOYEES = [
    {"name_en": "Chan Tai Man", "name_tc": "陳大文", "hkid_last4": "1234", "employment_type": "full_time", "start_date": "2023-06-01", "monthly_salary": 25000},
    {"name_en": "Wong Siu Ming", "name_tc": "黃小明", "hkid_last4": "5678", "employment_type": "full_time", "start_date": "2024-01-15", "monthly_salary": 18000},
    {"name_en": "Li Mei Ling", "name_tc": "李美玲", "hkid_last4": "9012", "employment_type": "part_time", "start_date": "2024-09-01", "monthly_salary": 8000},
    {"name_en": "Ho Ka Keung", "name_tc": "何家強", "hkid_last4": "3456", "employment_type": "full_time", "start_date": "2022-03-01", "monthly_salary": 35000},
    {"name_en": "Lam Wai Yee", "name_tc": "林慧儀", "hkid_last4": "7890", "employment_type": "casual", "start_date": "2026-01-20", "monthly_salary": 6000},
]

SAMPLE_PAYROLL = [
    {"emp_idx": 0, "basic_salary": 25000, "overtime": 0, "commission": 0, "bonus": 0},
    {"emp_idx": 1, "basic_salary": 18000, "overtime": 500, "commission": 0, "bonus": 0},
    {"emp_idx": 2, "basic_salary": 8000, "overtime": 0, "commission": 0, "bonus": 0},
    {"emp_idx": 3, "basic_salary": 35000, "overtime": 0, "commission": 2000, "bonus": 0},
]

# ---------------------------------------------------------------------------
# SupplierLedger sample data
# ---------------------------------------------------------------------------

SAMPLE_CONTACTS = [
    {"contact_type": "supplier", "company_name": "Roast & Co Coffee", "company_name_tc": "烘焙咖啡有限公司", "contact_person": "Tommy Kwok", "phone": "+85291110001", "whatsapp": "+85291110001", "email": "tommy@roastandco.hk", "payment_terms_days": 30},
    {"contact_type": "supplier", "company_name": "Wellcome Wholesale", "company_name_tc": "惠康批發", "contact_person": "Amy Ng", "phone": "+85291110002", "email": "wholesale@wellcome.hk", "payment_terms_days": 60},
    {"contact_type": "supplier", "company_name": "CLP Power Hong Kong", "company_name_tc": "中華電力香港", "contact_person": None, "phone": "+85228238888", "email": "billing@clp.com.hk", "payment_terms_days": 30},
    {"contact_type": "customer", "company_name": "ABC Trading Ltd", "company_name_tc": "ABC貿易有限公司", "contact_person": "Peter Cheung", "phone": "+85291110003", "whatsapp": "+85291110003", "email": "peter@abctrading.hk", "payment_terms_days": 30},
    {"contact_type": "customer", "company_name": "Golden Star Events", "company_name_tc": "金星活動策劃", "contact_person": "Winnie Lau", "phone": "+85291110004", "whatsapp": "+85291110004", "email": "winnie@goldenstar.hk", "payment_terms_days": 45},
    {"contact_type": "both", "company_name": "Metro Food Supply", "company_name_tc": "都會食品供應", "contact_person": "Raymond Yip", "phone": "+85291110005", "whatsapp": "+85291110005", "email": "raymond@metrofood.hk", "payment_terms_days": 30},
]

SAMPLE_INVOICES = [
    {"contact_idx": 0, "invoice_type": "payable", "invoice_number": "RC-2026-001", "days_ago": 45, "total_amount": 2800, "paid_amount": 0},
    {"contact_idx": 0, "invoice_type": "payable", "invoice_number": "RC-2026-002", "days_ago": 15, "total_amount": 3200, "paid_amount": 0},
    {"contact_idx": 1, "invoice_type": "payable", "invoice_number": "WW-2026-0156", "days_ago": 70, "total_amount": 5600, "paid_amount": 5600},
    {"contact_idx": 1, "invoice_type": "payable", "invoice_number": "WW-2026-0212", "days_ago": 20, "total_amount": 4200, "paid_amount": 0},
    {"contact_idx": 2, "invoice_type": "payable", "invoice_number": "CLP-FEB-2026", "days_ago": 10, "total_amount": 3200, "paid_amount": 3200},
    {"contact_idx": 3, "invoice_type": "receivable", "invoice_number": "INV-2026-001", "days_ago": 35, "total_amount": 8500, "paid_amount": 4000},
    {"contact_idx": 3, "invoice_type": "receivable", "invoice_number": "INV-2026-002", "days_ago": 10, "total_amount": 6200, "paid_amount": 0},
    {"contact_idx": 4, "invoice_type": "receivable", "invoice_number": "INV-2026-003", "days_ago": 60, "total_amount": 15000, "paid_amount": 0},
    {"contact_idx": 4, "invoice_type": "receivable", "invoice_number": "INV-2026-004", "days_ago": 5, "total_amount": 12000, "paid_amount": 0},
    {"contact_idx": 5, "invoice_type": "payable", "invoice_number": "MF-2026-088", "days_ago": 25, "total_amount": 7800, "paid_amount": 7800},
    {"contact_idx": 5, "invoice_type": "receivable", "invoice_number": "INV-2026-005", "days_ago": 12, "total_amount": 9500, "paid_amount": 0},
]

SAMPLE_PAYMENTS = [
    {"invoice_idx": 2, "amount": 5600, "payment_method": "bank_transfer", "bank_reference": "TRF-20260125-001", "days_ago": 30},
    {"invoice_idx": 4, "amount": 3200, "payment_method": "bank_transfer", "bank_reference": "TRF-20260228-005", "days_ago": 5},
    {"invoice_idx": 5, "amount": 4000, "payment_method": "cheque", "cheque_number": "CHQ-001234", "days_ago": 15},
    {"invoice_idx": 9, "amount": 7800, "payment_method": "fps", "bank_reference": "FPS-20260210-003", "days_ago": 12},
]

# ---------------------------------------------------------------------------
# SocialSync sample data
# ---------------------------------------------------------------------------

SAMPLE_POSTS = [
    {"content_text": "Happy Lunar New Year! Come try our special CNY set menu 🧧", "content_text_tc": "恭喜發財！快來試試我們的新年特別套餐 🧧", "hashtags": '["#hkfoodie","#cny2026","#hkig","#852food"]', "cta_text": "Book now via WhatsApp", "cta_link": "https://wa.me/85291234567", "status": "published", "days_ago": 20},
    {"content_text": "Fresh batch of our famous egg tarts just out of the oven! 🥧", "content_text_tc": "新鮮出爐嘅蛋撻！🥧", "hashtags": '["#eggtart","#hkfoodie","#hkig","#bakery"]', "cta_text": None, "cta_link": None, "status": "published", "days_ago": 14},
    {"content_text": "Weekend special: Buy 2 sets, get 1 free drink! Valid Sat & Sun only.", "content_text_tc": "週末優惠：買兩份套餐送飲品一杯！只限星期六日。", "hashtags": '["#hkdeals","#weekendspecial","#hkfood","#852"]', "cta_text": "Order via WhatsApp", "cta_link": "https://wa.me/85291234567", "status": "published", "days_ago": 7},
    {"content_text": "Our new matcha latte is here! Made with premium Uji matcha. 🍵", "content_text_tc": "全新抹茶拿鐵登場！選用頂級宇治抹茶。🍵", "hashtags": '["#matcha","#hkcafe","#hkig","#newmenu"]', "cta_text": None, "cta_link": None, "status": "scheduled", "days_ahead": 2},
    {"content_text": "Behind the scenes: Our baker starts at 5am every day to bring you the freshest pastries", "content_text_tc": "幕後花絮：我們的烘焙師每日清晨5點開始準備最新鮮的糕點", "hashtags": '["#behindthescenes","#hkbakery","#handmade","#hkfoodie"]', "cta_text": None, "cta_link": None, "status": "draft", "days_ahead": 0},
]

SAMPLE_PLATFORM_POSTS = [
    {"post_idx": 0, "platform": "instagram_feed", "publish_status": "published"},
    {"post_idx": 0, "platform": "facebook_page", "publish_status": "published"},
    {"post_idx": 1, "platform": "instagram_feed", "publish_status": "published"},
    {"post_idx": 1, "platform": "instagram_story", "publish_status": "published"},
    {"post_idx": 2, "platform": "instagram_feed", "publish_status": "published"},
    {"post_idx": 2, "platform": "facebook_page", "publish_status": "published"},
    {"post_idx": 2, "platform": "whatsapp_status", "publish_status": "published"},
]

SAMPLE_ANALYTICS = [
    {"pp_idx": 0, "impressions": 1250, "reach": 980, "likes": 87, "comments": 12, "shares": 5, "saves": 15},
    {"pp_idx": 1, "impressions": 890, "reach": 720, "likes": 45, "comments": 3, "shares": 2, "saves": 8},
    {"pp_idx": 2, "impressions": 2100, "reach": 1650, "likes": 156, "comments": 23, "shares": 18, "saves": 42},
    {"pp_idx": 3, "impressions": 1800, "reach": 1400, "likes": 120, "comments": 8, "shares": 12, "saves": 35},
    {"pp_idx": 4, "impressions": 3200, "reach": 2800, "likes": 245, "comments": 34, "shares": 28, "saves": 68},
    {"pp_idx": 5, "impressions": 1500, "reach": 1200, "likes": 89, "comments": 15, "shares": 10, "saves": 22},
    {"pp_idx": 6, "impressions": 450, "reach": 380, "likes": 0, "comments": 0, "shares": 0, "saves": 0},
]

SAMPLE_HASHTAGS = [
    {"hashtag": "#hkfoodie", "category": "food", "avg_engagement": 4.2, "language": "en"},
    {"hashtag": "#hkig", "category": "general", "avg_engagement": 3.8, "language": "en"},
    {"hashtag": "#852", "category": "general", "avg_engagement": 3.5, "language": "en"},
    {"hashtag": "#hongkong", "category": "general", "avg_engagement": 2.9, "language": "en"},
    {"hashtag": "#hklife", "category": "lifestyle", "avg_engagement": 3.1, "language": "en"},
    {"hashtag": "#hkcafe", "category": "food", "avg_engagement": 4.5, "language": "en"},
    {"hashtag": "#hkfood", "category": "food", "avg_engagement": 4.0, "language": "en"},
    {"hashtag": "#852food", "category": "food", "avg_engagement": 3.6, "language": "en"},
    {"hashtag": "#香港美食", "category": "food", "avg_engagement": 4.8, "language": "zh"},
    {"hashtag": "#打卡", "category": "general", "avg_engagement": 3.2, "language": "zh"},
    {"hashtag": "#hkdeals", "category": "promo", "avg_engagement": 5.1, "language": "en"},
    {"hashtag": "#weekendspecial", "category": "promo", "avg_engagement": 4.3, "language": "en"},
]

HK_SEASONAL_EVENTS = [
    {"date": "2026-02-14", "theme": "Valentine's Day", "is_hk_event": True, "event_name": "Valentine's Day"},
    {"date": "2026-02-17", "theme": "Chinese New Year", "is_hk_event": True, "event_name": "Chinese New Year"},
    {"date": "2026-04-05", "theme": "Easter / Ching Ming", "is_hk_event": True, "event_name": "Easter"},
    {"date": "2026-05-10", "theme": "Mother's Day", "is_hk_event": True, "event_name": "Mother's Day"},
    {"date": "2026-06-19", "theme": "Dragon Boat Festival", "is_hk_event": True, "event_name": "Dragon Boat Festival"},
    {"date": "2026-06-21", "theme": "Father's Day", "is_hk_event": True, "event_name": "Father's Day"},
    {"date": "2026-09-25", "theme": "Mid-Autumn Festival", "is_hk_event": True, "event_name": "Mid-Autumn Festival"},
    {"date": "2026-11-11", "theme": "Singles' Day (11.11)", "is_hk_event": True, "event_name": "Singles' Day"},
    {"date": "2026-11-27", "theme": "Black Friday", "is_hk_event": True, "event_name": "Black Friday"},
    {"date": "2026-12-25", "theme": "Christmas", "is_hk_event": True, "event_name": "Christmas"},
    {"date": "2026-12-31", "theme": "New Year's Eve", "is_hk_event": True, "event_name": "New Year's Eve"},
]


def seed_biz_owner_os(db_path: str | Path) -> int:
    """Seed BizOwner OS demo data: customers, sales, expenses, inventory, messages."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if existing > 0:
            logger.info("BizOwner OS already has data, skipping seed")
            return 0

        today = date.today()
        now = datetime.now()

        for c in SAMPLE_CUSTOMERS:
            last_visit = (today - timedelta(days=c["visit_count"])).isoformat()
            conn.execute(
                """INSERT INTO customers
                   (phone, name, name_tc, tags, total_spend, visit_count, last_visit)
                   VALUES (?,?,?,?,?,?,?)""",
                (c["phone"], c["name"], c["name_tc"], c["tags"],
                 c["total_spend"], c["visit_count"], last_visit),
            )
            count += 1

        for s in SAMPLE_SALES:
            sale_date = (now - timedelta(days=s["days_ago"])).isoformat()
            conn.execute(
                """INSERT INTO sales
                   (sale_date, total_amount, payment_method, items, customer_phone, pos_source)
                   VALUES (?,?,?,?,?,?)""",
                (sale_date, s["total_amount"], s["payment_method"],
                 s["items"], s["customer_phone"], s["pos_source"]),
            )
            count += 1

        for e in SAMPLE_EXPENSES:
            expense_date = (today - timedelta(days=e["days_ago"])).isoformat()
            conn.execute(
                """INSERT INTO expenses
                   (expense_date, category, description, amount, payment_method, recurring)
                   VALUES (?,?,?,?,?,?)""",
                (expense_date, e["category"], e["description"],
                 e["amount"], e["payment_method"], e["recurring"]),
            )
            count += 1

        for inv in SAMPLE_INVENTORY:
            conn.execute(
                """INSERT INTO inventory
                   (item_name, item_name_tc, current_stock, low_stock_threshold, unit_cost, last_updated)
                   VALUES (?,?,?,?,?,?)""",
                (inv["item_name"], inv["item_name_tc"], inv["current_stock"],
                 inv["low_stock_threshold"], inv["unit_cost"], now.isoformat()),
            )
            count += 1

        customer_ids = {
            r[0]: r[1]
            for r in conn.execute("SELECT phone, id FROM customers").fetchall()
        }
        for m in SAMPLE_MESSAGES:
            cust_id = customer_ids.get(m["phone"])
            ts = (now - timedelta(hours=m["hours_ago"])).isoformat()
            conn.execute(
                """INSERT INTO whatsapp_messages
                   (customer_id, direction, message_text, message_type, tags, requires_followup, timestamp)
                   VALUES (?,?,?,?,?,?,?)""",
                (cust_id, m["direction"], m["message_text"],
                 m["message_type"], m["tags"], m["requires_followup"], ts),
            )
            count += 1

    logger.info("Seeded %d BizOwner OS records", count)
    return count


def seed_mpf_calc(db_path: str | Path) -> int:
    """Seed MPFCalc demo data: employees, payroll records, contributions."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        if existing > 0:
            logger.info("MPFCalc already has data, skipping seed")
            return 0

        for emp in SAMPLE_EMPLOYEES:
            start = datetime.strptime(emp["start_date"], "%Y-%m-%d").date()
            enrollment = start + timedelta(days=60)
            conn.execute(
                """INSERT INTO employees
                   (name_en, name_tc, hkid_last4, employment_type, start_date,
                    mpf_enrollment_date, monthly_salary, active)
                   VALUES (?,?,?,?,?,?,?,1)""",
                (emp["name_en"], emp["name_tc"], emp["hkid_last4"],
                 emp["employment_type"], emp["start_date"],
                 enrollment.isoformat(), emp["monthly_salary"]),
            )
            count += 1

        emp_ids = [r[0] for r in conn.execute("SELECT id FROM employees ORDER BY id").fetchall()]

        today = date.today()
        for pr in SAMPLE_PAYROLL:
            eid = emp_ids[pr["emp_idx"]]
            total_income = pr["basic_salary"] + pr["overtime"] + pr["commission"] + pr["bonus"]

            income_d = Decimal(str(total_income))
            rate = Decimal("0.05")
            max_ri = Decimal("30000")
            min_ri = Decimal("7100")
            max_contrib = Decimal("1500")

            capped_income = min(income_d, max_ri)
            employer_mandatory = min(capped_income * rate, max_contrib)

            if income_d < min_ri:
                employee_mandatory = Decimal("0")
            else:
                employee_mandatory = min(capped_income * rate, max_contrib)

            employer_mandatory = employer_mandatory.quantize(Decimal("0.01"))
            employee_mandatory = employee_mandatory.quantize(Decimal("0.01"))
            total_contribution = employer_mandatory + employee_mandatory
            net_pay = income_d - employee_mandatory

            for months_back in range(3):
                month_date = (today.replace(day=1) - timedelta(days=30 * months_back)).replace(day=1)
                period_end = (month_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

                conn.execute(
                    """INSERT INTO payroll_records
                       (employee_id, pay_period_start, pay_period_end, basic_salary,
                        overtime, commission, bonus, total_relevant_income,
                        mpf_employee_deduction, net_pay)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (eid, month_date.isoformat(), period_end.isoformat(),
                     pr["basic_salary"], pr["overtime"], pr["commission"],
                     pr["bonus"], total_income,
                     float(employee_mandatory), float(net_pay)),
                )
                count += 1

                status = "paid" if months_back > 0 else "calculated"
                payment_date = (month_date + timedelta(days=40)).isoformat() if status == "paid" else None
                conn.execute(
                    """INSERT INTO monthly_contributions
                       (employee_id, contribution_month, relevant_income,
                        employer_mandatory, employee_mandatory, total_contribution,
                        payment_status, payment_date)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (eid, month_date.isoformat(), total_income,
                     float(employer_mandatory), float(employee_mandatory),
                     float(total_contribution), status, payment_date),
                )
                count += 1

    logger.info("Seeded %d MPFCalc records", count)
    return count


def seed_supplier_ledger(db_path: str | Path) -> int:
    """Seed SupplierLedger demo data: contacts, invoices, payments."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        if existing > 0:
            logger.info("SupplierLedger already has data, skipping seed")
            return 0

        for c in SAMPLE_CONTACTS:
            conn.execute(
                """INSERT INTO contacts
                   (contact_type, company_name, company_name_tc, contact_person,
                    phone, whatsapp, email, payment_terms_days)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (c["contact_type"], c["company_name"], c.get("company_name_tc"),
                 c.get("contact_person"), c.get("phone"), c.get("whatsapp"),
                 c.get("email"), c["payment_terms_days"]),
            )
            count += 1

        contact_ids = [r[0] for r in conn.execute("SELECT id FROM contacts ORDER BY id").fetchall()]
        today = date.today()

        invoice_ids = []
        for inv in SAMPLE_INVOICES:
            cid = contact_ids[inv["contact_idx"]]
            inv_date = today - timedelta(days=inv["days_ago"])
            terms = SAMPLE_CONTACTS[inv["contact_idx"]]["payment_terms_days"]
            due_date = inv_date + timedelta(days=terms)
            balance = inv["total_amount"] - inv["paid_amount"]

            if inv["paid_amount"] >= inv["total_amount"]:
                status = "paid"
            elif inv["paid_amount"] > 0:
                status = "partially_paid"
            elif due_date < today:
                status = "overdue"
            else:
                status = "outstanding"

            conn.execute(
                """INSERT INTO invoices
                   (contact_id, invoice_type, invoice_number, invoice_date, due_date,
                    total_amount, paid_amount, balance, status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (cid, inv["invoice_type"], inv["invoice_number"],
                 inv_date.isoformat(), due_date.isoformat(),
                 inv["total_amount"], inv["paid_amount"], balance, status),
            )
            invoice_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for p in SAMPLE_PAYMENTS:
            iid = invoice_ids[p["invoice_idx"]]
            pay_date = (today - timedelta(days=p["days_ago"])).isoformat()
            conn.execute(
                """INSERT INTO payments
                   (invoice_id, payment_date, amount, payment_method,
                    cheque_number, bank_reference)
                   VALUES (?,?,?,?,?,?)""",
                (iid, pay_date, p["amount"], p["payment_method"],
                 p.get("cheque_number"), p.get("bank_reference")),
            )
            count += 1

    logger.info("Seeded %d SupplierLedger records", count)
    return count


def seed_social_sync(db_path: str | Path) -> int:
    """Seed SocialSync demo data: posts, platform posts, analytics, calendar, hashtags."""
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        if existing > 0:
            logger.info("SocialSync already has data, skipping seed")
            return 0

        now = datetime.now()
        post_ids = []

        for p in SAMPLE_POSTS:
            if p["status"] in ("published", "draft"):
                ts = (now - timedelta(days=p.get("days_ago", 0))).isoformat()
                scheduled = None
            else:
                ts = now.isoformat()
                scheduled = (now + timedelta(days=p.get("days_ahead", 1))).isoformat()

            conn.execute(
                """INSERT INTO posts
                   (content_text, content_text_tc, hashtags, cta_text, cta_link,
                    scheduled_time, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (p["content_text"], p["content_text_tc"], p["hashtags"],
                 p.get("cta_text"), p.get("cta_link"), scheduled,
                 p["status"], ts),
            )
            post_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        pp_ids = []
        for pp in SAMPLE_PLATFORM_POSTS:
            pid = post_ids[pp["post_idx"]]
            published_at = (now - timedelta(days=SAMPLE_POSTS[pp["post_idx"]].get("days_ago", 0))).isoformat()
            conn.execute(
                """INSERT INTO platform_posts
                   (post_id, platform, publish_status, published_at)
                   VALUES (?,?,?,?)""",
                (pid, pp["platform"], pp["publish_status"], published_at),
            )
            pp_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            count += 1

        for a in SAMPLE_ANALYTICS:
            ppid = pp_ids[a["pp_idx"]]
            conn.execute(
                """INSERT INTO analytics
                   (platform_post_id, impressions, reach, likes, comments, shares, saves)
                   VALUES (?,?,?,?,?,?,?)""",
                (ppid, a["impressions"], a["reach"], a["likes"],
                 a["comments"], a["shares"], a["saves"]),
            )
            count += 1

        for event in HK_SEASONAL_EVENTS:
            conn.execute(
                """INSERT INTO content_calendar
                   (date, theme, is_hk_event, event_name)
                   VALUES (?,?,?,?)""",
                (event["date"], event["theme"], event["is_hk_event"], event["event_name"]),
            )
            count += 1

        for h in SAMPLE_HASHTAGS:
            conn.execute(
                """INSERT INTO hashtag_library
                   (hashtag, category, avg_engagement, usage_count, language)
                   VALUES (?,?,?,0,?)""",
                (h["hashtag"], h["category"], h["avg_engagement"], h["language"]),
            )
            count += 1

    logger.info("Seeded %d SocialSync records", count)
    return count


def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "biz_owner_os": seed_biz_owner_os(db_paths["bizowner"]),
        "mpf_calc": seed_mpf_calc(db_paths["mpf"]),
        "supplier_ledger": seed_supplier_ledger(db_paths["ledger"]),
        "social_sync": seed_social_sync(db_paths["socialsync"]),
    }
