export type OrderStatus =
  | "pending_payment"
  | "paid"
  | "hardware_pending"
  | "hardware_received"
  | "provisioning"
  | "testing"
  | "ready"
  | "shipped"
  | "delivered"
  | "completed";

export type HardwareType = "mac_mini_m4" | "imac_m4";

export type AddonCategory =
  | "fast"
  | "standard"
  | "think"
  | "coder"
  | "pro_bundle"
  | "max_bundle";

export type DeviceSetupStatus =
  | "registered"
  | "provisioning"
  | "testing"
  | "passed"
  | "failed"
  | "shipped";

export type TestStatus = "pass" | "fail" | "warning" | "skipped";

export type TestCategory =
  | "hardware"
  | "macos_environment"
  | "openclaw_core"
  | "llm_models"
  | "voice_system"
  | "security"
  | "stress_edge_cases";

export type UserRole = "client" | "admin" | "technician";

export interface Profile {
  id: string;
  role: UserRole;
  company_name: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  language_pref: "en" | "zh-hant" | "zh-hans";
  created_at: string;
  updated_at: string;
}

export interface OrderHardwareConfig {
  confirmation_code?: string;
  [key: string]: unknown;
}

export interface Order {
  id: string;
  client_id: string;
  status: OrderStatus;
  hardware_type: HardwareType;
  hardware_config: OrderHardwareConfig;
  software_package: string;
  total_price_hkd: number;
  stripe_payment_intent_id: string | null;
  stripe_checkout_session_id: string | null;
  delivery_address: string | null;
  notes: string | null;
  apple_order_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderAddon {
  id: string;
  order_id: string;
  addon_type: "model" | "bundle";
  addon_name: string;
  category: AddonCategory;
  price_hkd: number;
  created_at: string;
}

export interface OrderStatusHistory {
  id: string;
  order_id: string;
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  notes: string | null;
  updated_by: string | null;
  created_at: string;
}

export interface Device {
  id: string;
  order_id: string;
  serial_number: string | null;
  hardware_type: HardwareType;
  mac_address: string | null;
  setup_status: DeviceSetupStatus;
  technician_id: string | null;
  setup_started_at: string | null;
  setup_completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeviceTestResult {
  id: string;
  device_id: string;
  category: TestCategory;
  test_name: string;
  status: TestStatus;
  details: Record<string, unknown>;
  duration_ms: number | null;
  executed_at: string;
}

export interface DeviceTestSummary {
  id: string;
  device_id: string;
  total_tests: number;
  passed: number;
  failed: number;
  warnings: number;
  skipped: number;
  overall_status: TestStatus;
  full_report_json: Record<string, unknown>;
  created_at: string;
}

export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: Profile;
        Insert: Omit<Profile, "created_at" | "updated_at"> & {
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<Profile, "id">>;
        Relationships: [];
      };
      orders: {
        Row: Order;
        Insert: Omit<Order, "id" | "created_at" | "updated_at" | "status"> & {
          id?: string;
          status?: OrderStatus;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<Order, "id">>;
        Relationships: [];
      };
      order_addons: {
        Row: OrderAddon;
        Insert: Omit<OrderAddon, "id" | "created_at"> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<OrderAddon, "id">>;
        Relationships: [];
      };
      order_status_history: {
        Row: OrderStatusHistory;
        Insert: Omit<OrderStatusHistory, "id" | "created_at"> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<OrderStatusHistory, "id">>;
        Relationships: [];
      };
      devices: {
        Row: Device;
        Insert: Omit<Device, "id" | "created_at" | "updated_at" | "setup_status"> & {
          id?: string;
          setup_status?: DeviceSetupStatus;
          created_at?: string;
          updated_at?: string;
        };
        Update: Partial<Omit<Device, "id">>;
        Relationships: [];
      };
      device_test_results: {
        Row: DeviceTestResult;
        Insert: Omit<DeviceTestResult, "id" | "executed_at"> & {
          id?: string;
          executed_at?: string;
        };
        Update: Partial<Omit<DeviceTestResult, "id">>;
        Relationships: [];
      };
      device_test_summaries: {
        Row: DeviceTestSummary;
        Insert: Omit<DeviceTestSummary, "id" | "created_at"> & {
          id?: string;
          created_at?: string;
        };
        Update: Partial<Omit<DeviceTestSummary, "id">>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
}
