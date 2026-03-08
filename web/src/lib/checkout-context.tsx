"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import type { HardwareType } from "@/types/database";

export interface OrderState {
  hardwareType: HardwareType | null;
  hardwareConfig: {
    ssd?: string;
    color?: string;
    ethernet?: boolean;
  };
  addons: {
    models: string[];
    bundle: string | null;
  };
}

const DEFAULT_STATE: OrderState = {
  hardwareType: null,
  hardwareConfig: {},
  addons: { models: [], bundle: null },
};

interface CheckoutContextValue {
  order: OrderState;
  setHardware: (type: HardwareType, config?: OrderState["hardwareConfig"]) => void;
  setAddons: (addons: OrderState["addons"]) => void;
  resetOrder: () => void;
  currentStep: number;
  setCurrentStep: (step: number) => void;
}

const CheckoutContext = createContext<CheckoutContextValue | null>(null);

const STORAGE_KEY = "monoclaw_order";

export function CheckoutProvider({ children }: { children: ReactNode }) {
  const [order, setOrder] = useState<OrderState>(DEFAULT_STATE);
  const [currentStep, setCurrentStep] = useState(1);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        setOrder(JSON.parse(saved));
      }
    } catch {}
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (loaded) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(order));
    }
  }, [order, loaded]);

  const setHardware = useCallback((type: HardwareType, config?: OrderState["hardwareConfig"]) => {
    setOrder((prev) => ({ ...prev, hardwareType: type, hardwareConfig: config || {} }));
  }, []);

  const setAddons = useCallback((addons: OrderState["addons"]) => {
    setOrder((prev) => ({ ...prev, addons }));
  }, []);

  const resetOrder = useCallback(() => {
    setOrder(DEFAULT_STATE);
    setCurrentStep(1);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <CheckoutContext.Provider
      value={{ order, setHardware, setAddons, resetOrder, currentStep, setCurrentStep }}
    >
      {children}
    </CheckoutContext.Provider>
  );
}

export function useCheckout() {
  const ctx = useContext(CheckoutContext);
  if (!ctx) throw new Error("useCheckout must be used within CheckoutProvider");
  return ctx;
}
