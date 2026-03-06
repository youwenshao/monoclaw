"""Toolbox talk templates — bilingual EN/TC for HK construction hazards."""

from __future__ import annotations

import logging

logger = logging.getLogger("openclaw.construction.safety_form.reporting.toolbox")


_TALK_TEMPLATES: list[dict] = [
    {
        "id": "height_work",
        "topic_en": "Working at Height Safety",
        "topic_tc": "高空工作安全",
        "content_en": (
            "Key Points:\n"
            "1. Always wear a full-body harness with double lanyard when working above 2 metres\n"
            "2. Check all anchor points before use — minimum 15 kN capacity\n"
            "3. Guardrails must be at least 900mm high with mid-rail and toe board\n"
            "4. Never throw tools or materials from height — use tool lanyards and material hoists\n"
            "5. Report any damaged edge protection immediately\n\n"
            "Legal Reference: Factories & Industrial Undertakings (Lifting Appliances and Lifting Gear) Regulations"
        ),
        "content_tc": (
            "要點：\n"
            "1. 在2米以上高空工作時必須佩戴全身式安全帶及雙鈎繩\n"
            "2. 使用前檢查所有錨點 — 最低承重15千牛頓\n"
            "3. 護欄必須至少900毫米高，並設有中欄及踢腳板\n"
            "4. 嚴禁從高處拋擲工具或物料 — 使用工具繫繩及物料吊機\n"
            "5. 發現任何損壞的邊緣防護裝置須立即報告\n\n"
            "法律參考：工廠及工業經營（起重機械及起重裝置）規例"
        ),
        "duration_minutes": 15,
        "category": "fall_protection",
    },
    {
        "id": "bamboo_scaffold",
        "topic_en": "Bamboo Scaffolding Safety",
        "topic_tc": "竹棚架安全",
        "content_en": (
            "Key Points:\n"
            "1. Only competent bamboo scaffold workers (registered with CIC) may erect/dismantle\n"
            "2. Inspect all bamboo poles for cracks, insect damage, and adequate diameter\n"
            "3. Tie wires (galvanised #8) must be tight — check for loosening daily\n"
            "4. Working platforms must be at least 400mm wide with full planking\n"
            "5. Catch fans required at every 3 storeys on external scaffolding\n\n"
            "Legal Reference: Construction Sites (Safety) Regulations"
        ),
        "content_tc": (
            "要點：\n"
            "1. 只有合資格竹棚架工人（已在建造業議會註冊）方可搭建/拆卸\n"
            "2. 檢查所有竹桿有否裂紋、蟲蛀及直徑是否足夠\n"
            "3. 紮線（鍍鋅8號鐵線）必須紮緊 — 每日檢查有否鬆脫\n"
            "4. 工作平台必須至少400毫米闊並鋪設完整板面\n"
            "5. 外牆棚架每隔三層須設安全網\n\n"
            "法律參考：建築地盤（安全）規例"
        ),
        "duration_minutes": 15,
        "category": "scaffolding",
    },
    {
        "id": "confined_space",
        "topic_en": "Confined Space Entry",
        "topic_tc": "密閉空間進入",
        "content_en": (
            "Key Points:\n"
            "1. Never enter a confined space without a valid permit-to-work\n"
            "2. Atmospheric testing required: O₂ (19.5–23.5%), LEL (<10%), toxic gases\n"
            "3. Standby person must remain at entry point at all times\n"
            "4. Emergency rescue plan and equipment must be in place before entry\n"
            "5. Continuous ventilation required throughout the work period\n\n"
            "Legal Reference: Factories & Industrial Undertakings (Confined Spaces) Regulations"
        ),
        "content_tc": (
            "要點：\n"
            "1. 未持有效工作許可證不得進入密閉空間\n"
            "2. 須進行大氣測試：氧氣（19.5–23.5%）、可燃氣體下限（<10%）、有毒氣體\n"
            "3. 看守人必須全程留在入口\n"
            "4. 進入前必須備妥緊急救援計劃及設備\n"
            "5. 工作期間須持續通風\n\n"
            "法律參考：工廠及工業經營（密閉空間）規例"
        ),
        "duration_minutes": 20,
        "category": "confined_space",
    },
    {
        "id": "heat_stress",
        "topic_en": "Heat Stress Prevention",
        "topic_tc": "預防中暑",
        "content_en": (
            "Key Points:\n"
            "1. Monitor the Hong Kong Observatory heat stress at work warning\n"
            "2. Schedule heavy work during cooler hours (before 10am, after 3pm)\n"
            "3. Provide shaded rest areas and cool drinking water at all times\n"
            "4. Work-rest cycle: 45 min work / 15 min rest when WBGT >30°C\n"
            "5. Watch for heat illness signs: dizziness, nausea, confusion — stop work immediately\n\n"
            "Reference: Labour Department Guidelines on Heat Stress at Work"
        ),
        "content_tc": (
            "要點：\n"
            "1. 留意香港天文台工作暑熱警告\n"
            "2. 將繁重工作安排在較涼快時段（上午10時前、下午3時後）\n"
            "3. 隨時提供有遮蔭的休息區及清涼飲用水\n"
            "4. 工作休息循環：當WBGT >30°C時，工作45分鐘/休息15分鐘\n"
            "5. 注意中暑徵兆：頭暈、噁心、神志不清 — 立即停止工作\n\n"
            "參考：勞工處《工作暑熱警告》指引"
        ),
        "duration_minutes": 10,
        "category": "environmental",
    },
    {
        "id": "typhoon_prep",
        "topic_en": "Typhoon Preparedness",
        "topic_tc": "颱風防備",
        "content_en": (
            "Key Points:\n"
            "1. Monitor HKO tropical cyclone warnings — action plan for T3, T8, T10\n"
            "2. Secure all loose materials, signage, scaffolding ties before T3 hoisted\n"
            "3. Lower tower crane jibs to weathervane mode; secure all hoists\n"
            "4. Cover and secure all excavations — pump standby for flooding\n"
            "5. Post-typhoon inspection required before resuming work\n\n"
            "Reference: CIC Guidelines on Site Safety Measures for Working in Hot Weather and Typhoons"
        ),
        "content_tc": (
            "要點：\n"
            "1. 留意天文台熱帶氣旋警告 — 三號、八號、十號風球行動計劃\n"
            "2. 三號風球懸掛前固定所有鬆散物料、標誌牌、棚架紮線\n"
            "3. 將塔式起重機臂降至自由迴旋模式；固定所有起重機\n"
            "4. 覆蓋及固定所有掘坑 — 準備水泵防水浸\n"
            "5. 颱風過後須進行檢查方可復工\n\n"
            "參考：建造業議會《酷熱天氣及颱風下工地安全措施》指引"
        ),
        "duration_minutes": 15,
        "category": "emergency",
    },
    {
        "id": "manual_handling",
        "topic_en": "Manual Handling Operations",
        "topic_tc": "體力處理操作",
        "content_en": (
            "Key Points:\n"
            "1. Assess the load before lifting — if over 20kg, use mechanical aids or team lift\n"
            "2. Correct technique: bend knees, keep back straight, hold load close to body\n"
            "3. Clear the path before carrying — watch for uneven surfaces and obstructions\n"
            "4. Use trolleys, hoists, or forklifts for repetitive or heavy lifting\n"
            "5. Report any back pain or strain immediately\n\n"
            "Legal Reference: Occupational Safety & Health Regulations"
        ),
        "content_tc": (
            "要點：\n"
            "1. 提舉前先評估負荷 — 超過20公斤須使用機械輔助或合力搬運\n"
            "2. 正確姿勢：屈膝、背部挺直、負荷貼近身體\n"
            "3. 搬運前清理路線 — 注意不平路面及障礙物\n"
            "4. 重複或沉重搬運應使用手推車、吊機或叉車\n"
            "5. 出現背痛或拉傷須立即報告\n\n"
            "法律參考：職業安全及健康規例"
        ),
        "duration_minutes": 10,
        "category": "manual_handling",
    },
    {
        "id": "electrical_safety",
        "topic_en": "Electrical Safety on Site",
        "topic_tc": "工地電氣安全",
        "content_en": (
            "Key Points:\n"
            "1. All temporary electrical installations must be inspected by registered electrical worker\n"
            "2. Use 110V CTE (centre-tapped earth) supply for portable tools\n"
            "3. Check all cables, plugs, and connections before use — no damaged insulation\n"
            "4. Keep electrical equipment dry — use RCD protection on all circuits\n"
            "5. Maintain safe distance from overhead power lines (minimum 4m for up to 132kV)\n\n"
            "Legal Reference: Electricity Supply Lines (Protection) Regulation"
        ),
        "content_tc": (
            "要點：\n"
            "1. 所有臨時電力裝置須由註冊電業工程人員檢查\n"
            "2. 手提工具須使用110伏特中間接地供電系統\n"
            "3. 使用前檢查所有電線、插頭及接駁位 — 絕緣不可損壞\n"
            "4. 保持電氣設備乾燥 — 所有電路須裝設漏電斷路器\n"
            "5. 與架空電纜保持安全距離（132千伏以下最少4米）\n\n"
            "法律參考：電力供應線路（保護）規例"
        ),
        "duration_minutes": 15,
        "category": "electrical",
    },
]


def get_talk_templates(language: str = "en") -> list[dict]:
    """Return toolbox talk templates in the requested language.

    Parameters:
        language: 'en' for English, 'tc' for Traditional Chinese
    """
    result = []
    for t in _TALK_TEMPLATES:
        if language == "tc":
            topic = t["topic_tc"]
            content = t["content_tc"]
        else:
            topic = t["topic_en"]
            content = t["content_en"]

        result.append({
            "id": t["id"],
            "topic": topic,
            "content": content,
            "duration_minutes": t["duration_minutes"],
            "category": t["category"],
        })

    logger.debug("Returning %d talk templates (lang=%s)", len(result), language)
    return result


def get_talk_by_id(talk_id: str, language: str = "en") -> dict | None:
    """Look up a single talk template by its ID."""
    for t in _TALK_TEMPLATES:
        if t["id"] == talk_id:
            if language == "tc":
                return {"id": t["id"], "topic": t["topic_tc"], "content": t["content_tc"],
                        "duration_minutes": t["duration_minutes"], "category": t["category"]}
            return {"id": t["id"], "topic": t["topic_en"], "content": t["content_en"],
                    "duration_minutes": t["duration_minutes"], "category": t["category"]}
    return None
