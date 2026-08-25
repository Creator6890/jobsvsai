import type { Occupation } from "@/types/occupation";

export type ActionRiskBand = "low" | "medium" | "high";

export type ActionPlanPriority = {
  order: number;
  title: string;
  guidance: string;
};

export type TaskActionItem = {
  name: string;
  exposure: number;
  automationFeasibility: number;
  augmentationPotential: number;
  importance: "High" | "Medium" | "Low";
  guidance: string;
  tag?: string;
};

export type ActionPlanData = {
  occupation: Occupation;
  riskBand: ActionRiskBand;
  bandTitle: string;
  bandDescription: string;
  priorities: ActionPlanPriority[];
  leanInto: {
    title: string;
    description: string;
    characteristics: string[];
    tasks: TaskActionItem[];
  };
  useAiFor: {
    title: string;
    description: string;
    tasks: TaskActionItem[];
  };
  watchClosely: {
    title: string;
    description: string;
    tasks: TaskActionItem[];
  };
  alternatives: {
    title: string;
    description: string;
    transitionProminence: "prominent" | "secondary";
    transitionCount: number;
    hasTransitions: boolean;
  };
};
