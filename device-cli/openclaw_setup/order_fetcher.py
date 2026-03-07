"""Fetch full order specification from Supabase for device provisioning."""

from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from supabase import Client

console = Console()

INDUSTRY_SOFTWARE_STACKS: dict[str, list[str]] = {
    "real-estate": ["PropertyGPT", "ListingSync Agent", "TenancyDoc Automator", "ViewingBot"],
    "immigration": ["VisaDoc OCR", "FormAutoFill", "PolicyWatcher", "ClientPortal Bot"],
    "fnb-hospitality": ["TableMaster AI", "NoShowShield", "QueueBot", "SommelierMemory"],
    "accounting": ["InvoiceOCR Pro", "ReconcileAgent", "TaxCalendar Bot", "FXTracker"],
    "legal": ["LegalDoc Analyzer", "DiscoveryAssistant", "DeadlineGuardian", "IntakeBot"],
    "medical-dental": ["ClinicScheduler", "MedReminder Bot", "ScribeAI", "InsuranceAgent"],
    "construction": ["PermitTracker", "SafetyForm Bot", "DefectsManager", "SiteCoordinator"],
    "import-export": ["TradeDoc AI", "SupplierBot", "StockReconcile", "FXInvoice"],
}

PERSONA_SOFTWARE_STACKS: dict[str, list[str]] = {
    "academic-researcher": ["PaperSieve", "CiteBot", "TranslateAssist", "GrantTracker"],
    "vibe-coder": ["CodeQwen-9B", "HKDevKit", "DocuWriter", "GitAssistant"],
    "solopreneur": ["BizOwner OS", "MPFCalc", "SocialSync", "SupplierLedger"],
    "curious-student": ["StudyBuddy", "InterviewPrep", "JobTracker", "ThesisFormatter"],
}

ALL_MODEL_IDS = [
    "qwen-3.5-0.8b", "deepseek-r1-1.5b", "llama-3.1-1b", "smollm2-1.7b", "gemma-3-1b",
    "deepseek-r1-7b", "llama-3.2-3b", "mistral-7b", "ministral-3b", "gemma-3-4b",
    "qwen-3.5-9b", "glm-4-9b", "llama-3.1-8b", "ministral-8b",
    "qwen-2.5-coder-7b", "deepseek-coder-6.7b",
]

MODEL_HF_REPOS: dict[str, str] = {
    "qwen-3.5-0.8b": "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
    "deepseek-r1-1.5b": "mlx-community/DeepSeek-R1-Distill-Qwen-1.5B-4bit",
    "llama-3.1-1b": "mlx-community/Llama-3.2-1B-Instruct-4bit",
    "smollm2-1.7b": "mlx-community/SmolLM2-1.7B-Instruct-4bit",
    "gemma-3-1b": "mlx-community/gemma-3-1b-it-4bit",
    "deepseek-r1-7b": "mlx-community/DeepSeek-R1-Distill-Qwen-7B-4bit",
    "llama-3.2-3b": "mlx-community/Llama-3.2-3B-Instruct-4bit",
    "mistral-7b": "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
    "ministral-3b": "mlx-community/Ministral-3b-instruct-4bit",
    "gemma-3-4b": "mlx-community/gemma-3-4b-it-4bit",
    "qwen-3.5-9b": "mlx-community/Qwen2.5-7B-Instruct-4bit",
    "glm-4-9b": "mlx-community/glm-4-9b-chat-4bit",
    "llama-3.1-8b": "mlx-community/Llama-3.1-8B-Instruct-4bit",
    "ministral-8b": "mlx-community/Ministral-8B-Instruct-2410-4bit",
    "qwen-2.5-coder-7b": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "deepseek-coder-6.7b": "mlx-community/deepseek-coder-6.7b-instruct-4bit",
}

MODEL_CATEGORY_MAP: dict[str, str] = {
    "qwen-3.5-0.8b": "fast", "deepseek-r1-1.5b": "fast", "llama-3.1-1b": "fast",
    "smollm2-1.7b": "fast", "gemma-3-1b": "fast",
    "deepseek-r1-7b": "standard", "llama-3.2-3b": "standard", "mistral-7b": "standard",
    "ministral-3b": "standard", "gemma-3-4b": "standard",
    "qwen-3.5-9b": "think", "glm-4-9b": "think", "llama-3.1-8b": "think", "ministral-8b": "think",
    "qwen-2.5-coder-7b": "coder", "deepseek-coder-6.7b": "coder",
}

ROUTING_COMPLEXITY_MAP = {
    "simple": ["fast"],
    "moderate": ["standard"],
    "complex": ["think"],
    "code": ["coder"],
}


@dataclass
class LlmPlan:
    plan_type: str  # "bundle", "alacarte", "api_only"
    bundle_id: Optional[str] = None
    model_ids: list[str] = field(default_factory=list)


@dataclass
class OrderSpec:
    order_id: str
    client_email: Optional[str]
    hardware_type: str
    hardware_config: dict
    industry: Optional[str]
    personas: list[str]
    llm_plan: LlmPlan
    industry_software: list[str] = field(default_factory=list)
    persona_software: list[str] = field(default_factory=list)


class OrderFetcher:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    def fetch_by_order_id(self, order_id: str) -> OrderSpec:
        console.print(f"[bold]Fetching order spec for {order_id}...[/bold]")

        order = self.supabase.table("orders").select("*").eq("id", order_id).execute()
        if not order.data:
            raise ValueError(f"Order {order_id} not found")
        order_row = order.data[0]

        addons = self.supabase.table("order_addons").select("*").eq("order_id", order_id).execute()

        client_email = self._get_client_email(order_row["client_id"])
        llm_plan = self._build_llm_plan(addons.data or [])

        industry = order_row.get("industry")
        personas = order_row.get("personas") or []

        industry_sw = INDUSTRY_SOFTWARE_STACKS.get(industry, []) if industry else []
        persona_sw = []
        for p in personas:
            persona_sw.extend(PERSONA_SOFTWARE_STACKS.get(p, []))

        spec = OrderSpec(
            order_id=order_id,
            client_email=client_email,
            hardware_type=order_row["hardware_type"],
            hardware_config=order_row.get("hardware_config") or {},
            industry=industry,
            personas=personas,
            llm_plan=llm_plan,
            industry_software=industry_sw,
            persona_software=persona_sw,
        )

        self._print_summary(spec)
        return spec

    def fetch_by_email(self, email: str) -> OrderSpec:
        console.print(f"[bold]Looking up order for {email}...[/bold]")

        users = self.supabase.auth.admin.list_users()
        user_id = None
        for u in users:
            if hasattr(u, "__iter__"):
                for user in u if isinstance(u, list) else []:
                    if hasattr(user, "email") and user.email == email:
                        user_id = user.id
                        break
            if user_id:
                break

        if not user_id:
            raise ValueError(f"No user found with email {email}")

        orders = (
            self.supabase.table("orders")
            .select("*")
            .eq("client_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not orders.data:
            raise ValueError(f"No orders found for user {email}")

        return self.fetch_by_order_id(orders.data[0]["id"])

    def _get_client_email(self, client_id: str) -> Optional[str]:
        if client_id == "00000000-0000-0000-0000-000000000000":
            return None
        try:
            user = self.supabase.auth.admin.get_user_by_id(client_id)
            return user.user.email if user and user.user else None
        except Exception:
            return None

    def _build_llm_plan(self, addons: list[dict]) -> LlmPlan:
        if not addons:
            return LlmPlan(plan_type="api_only")

        bundle = next((a for a in addons if a["addon_type"] == "bundle"), None)
        if bundle:
            bundle_id = bundle["addon_name"]
            if bundle_id == "max_bundle":
                return LlmPlan(plan_type="bundle", bundle_id=bundle_id, model_ids=list(ALL_MODEL_IDS))
            elif bundle_id == "pro_bundle":
                model_addons = [a for a in addons if a["addon_type"] == "model"]
                model_ids = [a["addon_name"] for a in model_addons] if model_addons else []
                return LlmPlan(plan_type="bundle", bundle_id=bundle_id, model_ids=model_ids)

        model_ids = [a["addon_name"] for a in addons if a["addon_type"] == "model"]
        return LlmPlan(plan_type="alacarte", model_ids=model_ids)

    def _print_summary(self, spec: OrderSpec):
        console.print(f"\n  [cyan]Hardware:[/cyan]     {spec.hardware_type}")
        console.print(f"  [cyan]Industry:[/cyan]     {spec.industry or 'None'}")
        console.print(f"  [cyan]Personas:[/cyan]     {', '.join(spec.personas) if spec.personas else 'None'}")
        console.print(f"  [cyan]LLM Plan:[/cyan]     {spec.llm_plan.plan_type}" +
                       (f" ({spec.llm_plan.bundle_id})" if spec.llm_plan.bundle_id else ""))
        console.print(f"  [cyan]Models:[/cyan]       {len(spec.llm_plan.model_ids)} model(s)")
        if spec.industry_software:
            console.print(f"  [cyan]Industry SW:[/cyan]  {', '.join(spec.industry_software)}")
        if spec.persona_software:
            console.print(f"  [cyan]Persona SW:[/cyan]   {', '.join(spec.persona_software)}")
        console.print()
