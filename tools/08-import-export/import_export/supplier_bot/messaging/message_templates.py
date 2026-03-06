"""Pre-defined bilingual message templates for supplier communication."""

from __future__ import annotations


_TEMPLATES: dict[str, dict[str, str]] = {
    "production_update_request": {
        "en": (
            "Dear {contact_name},\n\n"
            "We would like to request an update on order {order_ref}.\n"
            "Could you please provide the current production status, "
            "estimated completion date, and any photos if available?\n\n"
            "Thank you for your cooperation.\n"
            "Best regards,\n{sender_name}"
        ),
        "cn": (
            "{contact_name} 您好，\n\n"
            "我们想了解订单 {order_ref} 的最新生产情况。\n"
            "麻烦您提供目前的生产进度、预计完成日期，"
            "如有现场照片也请一并发送。\n\n"
            "感谢您的配合！\n{sender_name}"
        ),
    },
    "qc_request": {
        "en": (
            "Dear {contact_name},\n\n"
            "Order {order_ref} is approaching the QC stage.\n"
            "Please arrange for quality inspection and share the QC report "
            "once it's ready.  We need to confirm the following:\n"
            "  - Product dimensions and weight\n"
            "  - Colour / material match with approved sample\n"
            "  - Functional testing results\n\n"
            "Best regards,\n{sender_name}"
        ),
        "cn": (
            "{contact_name} 您好，\n\n"
            "订单 {order_ref} 即将进入质检阶段。\n"
            "请安排质量检验并在完成后分享质检报告。我们需要确认以下内容：\n"
            "  - 产品尺寸和重量\n"
            "  - 颜色/材料是否与批准样品一致\n"
            "  - 功能测试结果\n\n"
            "谢谢！\n{sender_name}"
        ),
    },
    "shipping_arrangement": {
        "en": (
            "Dear {contact_name},\n\n"
            "Please proceed with shipping arrangements for order {order_ref}.\n"
            "Kindly provide:\n"
            "  - Packing list\n"
            "  - Commercial invoice\n"
            "  - Shipping marks / container number\n"
            "  - Estimated departure and arrival dates\n\n"
            "Best regards,\n{sender_name}"
        ),
        "cn": (
            "{contact_name} 您好，\n\n"
            "请安排订单 {order_ref} 的发货事宜。\n"
            "请提供以下资料：\n"
            "  - 装箱单\n"
            "  - 商业发票\n"
            "  - 唛头/柜号\n"
            "  - 预计出货和到港日期\n\n"
            "谢谢！\n{sender_name}"
        ),
    },
    "payment_confirmation": {
        "en": (
            "Dear {contact_name},\n\n"
            "We have arranged {payment_type} of {amount} {currency} "
            "for order {order_ref}.\n"
            "Bank reference: {bank_ref}\n"
            "Please confirm receipt at your earliest convenience.\n\n"
            "Best regards,\n{sender_name}"
        ),
        "cn": (
            "{contact_name} 您好，\n\n"
            "我们已安排订单 {order_ref} 的{payment_type}，"
            "金额为 {amount} {currency}。\n"
            "银行参考编号：{bank_ref}\n"
            "请查收并确认。\n\n"
            "谢谢！\n{sender_name}"
        ),
    },
    "general_greeting": {
        "en": (
            "Dear {contact_name},\n\n"
            "Hope this message finds you well.\n"
            "{message_body}\n\n"
            "Best regards,\n{sender_name}"
        ),
        "cn": (
            "{contact_name} 您好，\n\n"
            "{message_body}\n\n"
            "此致敬礼，\n{sender_name}"
        ),
    },
}


class MessageTemplates:
    """Bilingual template manager for common supplier messages."""

    @staticmethod
    def get_template(template_type: str, language: str = "en") -> str:
        """Return the raw template string for a given type and language.

        Raises ``KeyError`` if *template_type* is unknown or *language* is
        not available for that template.
        """
        lang_key = "cn" if language.startswith("zh") or language == "cn" else "en"
        if template_type not in _TEMPLATES:
            raise KeyError(f"Unknown template type: {template_type}")
        if lang_key not in _TEMPLATES[template_type]:
            raise KeyError(f"Language '{lang_key}' not available for template '{template_type}'")
        return _TEMPLATES[template_type][lang_key]

    @staticmethod
    def render_template(template_type: str, language: str = "en", **kwargs: str) -> str:
        """Render a template with the provided keyword arguments.

        Missing placeholders are left as-is (``{placeholder}``) so callers
        can see which fields still need filling.
        """
        raw = MessageTemplates.get_template(template_type, language)
        try:
            return raw.format(**kwargs)
        except KeyError:
            import re
            needed = set(re.findall(r"\{(\w+)\}", raw))
            filled = {k: kwargs.get(k, "{" + k + "}") for k in needed}
            return raw.format(**filled)

    @staticmethod
    def available_templates() -> list[str]:
        return list(_TEMPLATES.keys())
