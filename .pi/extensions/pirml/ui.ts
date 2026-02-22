export interface UI {
  notify(msg: string, type: "info" | "error" | "warn"): void;
  setStatus(id: string, label: string): void;
  clearStatus(id: string): void;
}

export function createUIAdapter(piUI: any): UI {
  return {
    notify(msg, type) {
      piUI.notify(msg, type);
    },
    setStatus(id, label) {
      piUI.setStatus(id, label);
    },
    clearStatus(id) {
      piUI.clearStatus(id);
    },
  };
}
