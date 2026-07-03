import { create } from "zustand";
import type { ScheduleCommand } from "../api/scheduleCommandApi";

type HistoryState = {
  commandHistory: ScheduleCommand[];
  redoStack: ScheduleCommand[];
  recordCommand: (command: ScheduleCommand) => void;
};

export const useHistoryStore = create<HistoryState>((set) => ({
  commandHistory: [],
  redoStack: [],
  recordCommand: (command) =>
    set((state) => ({
      commandHistory: [...state.commandHistory, command],
      redoStack: []
    }))
}));
