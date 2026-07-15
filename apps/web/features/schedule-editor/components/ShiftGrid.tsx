import { Lock, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import type { ScheduleCommand } from "../api/scheduleCommandApi";
import type { ShiftSegment, WorkspaceData } from "../types";
import { useEditingStore } from "../store/editingStore";
import { useProposalStore } from "../store/proposalStore";
import { useSelectionStore } from "../store/selectionStore";
import { useWarningStore } from "../store/warningStore";
import { positionDisplayLabel } from "../utils/positionLabels";

type ShiftGridProps = {
  workspace?: WorkspaceData;
  isLoading: boolean;
  isReadOnly?: boolean;
  selectedDate?: string;
};

export function ShiftGrid({ workspace, isLoading, isReadOnly = false, selectedDate }: ShiftGridProps) {
  const selection = useSelectionStore((state) => state.selection);
  const hoveredSegmentId = useSelectionStore((state) => state.hoveredSegmentId);
  const scrollTargetSegmentId = useSelectionStore((state) => state.scrollTargetSegmentId);
  const selectShiftSegment = useSelectionStore((state) => state.selectShiftSegment);
  const setHoveredSegment = useSelectionStore((state) => state.setHoveredSegment);
  const requestSegmentScroll = useSelectionStore((state) => state.requestSegmentScroll);
  const activeProposalSegmentIds = useProposalStore((state) => state.activeProposalSegmentIds);
  const activeWarningSegmentId = useWarningStore((state) => state.activeWarningSegmentId);
  const pendingCommands = useEditingStore((state) => state.pendingCommands);
  const workShiftDrafts = useEditingStore((state) => state.workShiftDrafts);
  const queueCommand = useEditingStore((state) => state.queueCommand);
  const [segmentMenu, setSegmentMenu] = useState<SegmentMenuState | null>(null);
  const [emptySlotMenu, setEmptySlotMenu] = useState<EmptySlotMenuState | null>(null);
  const [mergeSelection, setMergeSelection] = useState<string[]>([]);
  const gridViewportRef = useRef<HTMLElement | null>(null);
  const [gridViewportWidth, setGridViewportWidth] = useState(0);

  useEffect(() => {
    if (!scrollTargetSegmentId) {
      return;
    }
    const element = document.querySelector(`[data-segment-id="${scrollTargetSegmentId}"]`);
    element?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    const timeoutId = window.setTimeout(() => requestSegmentScroll(null), 500);
    return () => window.clearTimeout(timeoutId);
  }, [requestSegmentScroll, scrollTargetSegmentId]);

  useEffect(() => {
    const element = gridViewportRef.current;
    if (!element) {
      return;
    }
    const updateWidth = () => setGridViewportWidth(element.clientWidth);
    updateWidth();
    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(element);
    return () => resizeObserver.disconnect();
  }, []);

  if (isLoading) {
    return <div className="min-h-0 overflow-auto bg-white p-4 text-sm text-neutral-500">読み込み中</div>;
  }
  if (!workspace) {
    return <div className="min-h-0 overflow-auto bg-white p-4 text-sm text-neutral-500">データがありません</div>;
  }

  const draftWorkspace = applyDraftCommands(workspace, pendingCommands, workShiftDrafts);
  const visibleWorkShifts = selectedDate
    ? draftWorkspace.work_shifts.filter((shift) => shift.work_date === selectedDate)
    : draftWorkspace.work_shifts;
  const visibleWorkShiftIds = new Set(visibleWorkShifts.map((shift) => shift.id));
  const visibleShiftSegments = draftWorkspace.shift_segments.filter((segment) => visibleWorkShiftIds.has(segment.work_shift_id));
  const visibleShiftRequests = selectedDate
    ? draftWorkspace.shift_requests.filter((request) => request.request_date === selectedDate)
    : draftWorkspace.shift_requests;
  const visibleWorkspace = {
    ...draftWorkspace,
    work_shifts: visibleWorkShifts,
    shift_requests: visibleShiftRequests,
    shift_segments: visibleShiftSegments
  };
  const timeline = buildTimeline(visibleWorkspace);
  const hourWidth = responsiveHourWidth(timeline.hours.length, gridViewportWidth);
  const timelineWidth = timeline.hours.length * hourWidth;
  const shiftsByStaff = groupShiftsByStaff(visibleWorkspace);
  const orderedStaffMembers = orderStaffForShiftGrid(draftWorkspace.staff_members, shiftsByStaff);
  const requestsByStaff = groupRequestsByStaff(visibleWorkspace, selectedDate);
  const warningCountBySegment = countWarningsBySegment(workspace);
  const openSegmentMenu = (
    event: MouseEvent<HTMLElement>,
    shift: WorkspaceData["work_shifts"][number],
    segment: ShiftSegment,
    splitTime?: string | null
  ) => {
    event.preventDefault();
    event.stopPropagation();
    selectShiftSegment(segment.id);
    if (isReadOnly) {
      setSegmentMenu(null);
      return;
    }
    setSegmentMenu({
      left: Math.min(event.clientX, window.innerWidth - 190),
      mergeTarget: mergeTargetForSegment(
        visibleShiftSegments
          .filter((item) => item.work_shift_id === shift.id)
          .sort((a, b) => a.start_time.localeCompare(b.start_time)),
        segment
      ),
      segment,
      shift,
      splitTime: splitTime ?? splitTimeFromSegmentPointer(event, segment),
      top: Math.min(event.clientY, window.innerHeight - 190)
    });
  };
  const queueCommandWithAutoMerge = (command: ScheduleCommand, affectedSegmentId?: string) => {
    queueCommand(command);
    const mergeCommands = autoMergeCommandsAfterCommand(
      workspace,
      pendingCommands,
      workShiftDrafts,
      command,
      affectedSegmentId
    );
    for (const mergeCommand of mergeCommands) {
      queueCommand(mergeCommand);
    }
  };
  const mergeCommands = mergeCommandsForSelection(visibleShiftSegments, mergeSelection);
  const mergeAnchorId = mergeAnchorSegmentId(visibleShiftSegments, mergeSelection);
  const clearMergeSelection = () => setMergeSelection([]);
  const toggleMergeSelection = (shiftId: string, segment: ShiftSegment) => {
    const sameShiftSelection = mergeSelection.every((segmentId) => {
      const selectedSegment = visibleShiftSegments.find((item) => item.id === segmentId);
      return selectedSegment?.work_shift_id === shiftId;
    });
    if (!sameShiftSelection || mergeSelection.length === 0) {
      setMergeSelection([segment.id]);
      return;
    }
    if (mergeSelection.includes(segment.id)) {
      setMergeSelection(mergeSelection.length === 1 ? [segment.id] : mergeSelection.filter((id) => id !== segment.id));
      return;
    }
    setMergeSelection([...mergeSelection, segment.id]);
  };

  return (
    <section ref={gridViewportRef} className="min-h-0 overflow-auto bg-white text-neutral-950">
      <div
        className="sticky top-0 z-20 grid border-b bg-neutral-50 text-xs text-neutral-500"
        style={{ gridTemplateColumns: `${STAFF_COLUMN_WIDTH}px ${timelineWidth}px` }}
      >
        <div className="sticky left-0 z-30 border-r bg-neutral-50 p-2 font-medium shadow-[1px_0_0_#e5e5e5]">
          従業員番号
        </div>
        <div className="grid" style={{ gridTemplateColumns: `repeat(${timeline.hours.length}, ${hourWidth}px)` }}>
          {timeline.hours.map((hour) => (
            <div className="border-r p-2 text-center tabular-nums" key={hour}>
              {formatHour(hour)}
            </div>
          ))}
        </div>
      </div>
      {mergeSelection.length >= 2 && (
        <div className="sticky top-10 z-20 flex items-center gap-2 border-b bg-white/95 px-3 py-2 text-xs shadow-sm backdrop-blur">
          <span className="font-medium">{mergeSelection.length}個のセルを選択中</span>
          <button
            className="rounded bg-neutral-950 px-3 py-1.5 font-semibold text-white disabled:cursor-not-allowed disabled:bg-neutral-300"
            disabled={mergeCommands.length === 0 || isReadOnly}
            onClick={() => {
              for (const command of mergeCommands) {
                queueCommand(command);
              }
              if (mergeAnchorId) {
                selectShiftSegment(mergeAnchorId);
              }
              clearMergeSelection();
            }}
            type="button"
          >
            選択セルを結合
          </button>
          {mergeCommands.length === 0 && (
            <span className="text-neutral-500">隣り合う同じ種類・同じポジションだけ結合できます。</span>
          )}
          <button className="rounded border px-2 py-1" onClick={clearMergeSelection} type="button">
            解除
          </button>
        </div>
      )}
      <div className="divide-y">
        {visibleWorkShifts.length === 0 ? (
          <div className="p-8 text-center text-sm text-neutral-500">
            {selectedDate
              ? `${formatDateWithWeekday(selectedDate)} の勤務はまだありません。シフト案作成画面で希望を入力し、AI提案を作成してください。`
              : "このScheduleVersionにはまだ勤務がありません。シフト案作成画面で希望を入力し、AI提案を作成してください。"}
          </div>
        ) : (
          orderedStaffMembers.map((staff) => {
            const shifts = shiftsByStaff.get(staff.id) ?? [];
            const isSelectedStaff =
              selection?.type === "workShift"
              && shifts.some((shift) => shift.id === selection.id);
            return (
              <div
                className={`grid min-h-24 ${isSelectedStaff ? "bg-amber-50 ring-2 ring-inset ring-amber-400" : ""}`}
                key={staff.id}
                style={{ gridTemplateColumns: `${STAFF_COLUMN_WIDTH}px ${timelineWidth}px` }}
              >
                <div className={`sticky left-0 z-10 border-r p-3 text-left shadow-[1px_0_0_#e5e5e5] ${isSelectedStaff ? "bg-amber-100" : "bg-neutral-50"}`}>
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${isSelectedStaff ? "bg-amber-500" : "bg-emerald-500"}`} />
                    <div className="text-sm font-semibold">{staff.employee_number ?? staffDisplayName(staff)}</div>
                  </div>
                  <div className="mt-1 pl-4 text-xs text-neutral-500">{staffDisplayName(staff)}</div>
                </div>
                <div
                  className="relative min-h-24 bg-[linear-gradient(to_right,#e5e5e5_1px,transparent_1px)]"
                  data-staff-id={staff.id}
                  onClick={(event) => {
                    if (event.target === event.currentTarget) {
                      clearMergeSelection();
                      setSegmentMenu(null);
                      if (isReadOnly || !selectedDate) {
                        return;
                      }
                      const startMinute = snapMinute(
                        minuteFromClientX(event.clientX, event.currentTarget, timeline),
                        timeline.startMinute,
                        timeline.totalMinutes
                      );
                      const defaultEndMinute = Math.min(
                        timeline.startMinute + timeline.totalMinutes,
                        startMinute + 60
                      );
                      setEmptySlotMenu({
                        date: selectedDate,
                        left: Math.min(event.clientX, window.innerWidth - 220),
                        startTime: minuteToTime(startMinute),
                        endTime: minuteToTime(defaultEndMinute),
                        staff,
                        top: Math.min(event.clientY, window.innerHeight - 230)
                      });
                    }
                  }}
                  onContextMenu={(event) => {
                    if (event.target !== event.currentTarget) {
                      return;
                    }
                    event.preventDefault();
                    clearMergeSelection();
                    setSegmentMenu(null);
                    if (isReadOnly || !selectedDate) {
                      return;
                    }
                    const startMinute = snapMinute(
                      minuteFromClientX(event.clientX, event.currentTarget, timeline),
                      timeline.startMinute,
                      timeline.totalMinutes
                    );
                    const defaultEndMinute = Math.min(
                      timeline.startMinute + timeline.totalMinutes,
                      startMinute + 60
                    );
                    setEmptySlotMenu({
                      date: selectedDate,
                      left: Math.min(event.clientX, window.innerWidth - 220),
                      startTime: minuteToTime(startMinute),
                      endTime: minuteToTime(defaultEndMinute),
                      staff,
                      top: Math.min(event.clientY, window.innerHeight - 230)
                    });
                  }}
                  style={{ backgroundSize: `${hourWidth}px 100%` }}
                >
                  {shifts.map((shift) => (
                    <div
                      className={`absolute top-5 h-14 ${selection?.type === "workShift" && selection.id === shift.id ? "rounded ring-4 ring-amber-400 ring-offset-2" : ""}`}
                      key={shift.id}
                      onClick={(event) => {
                        clearMergeSelection();
                        setSegmentMenu(null);
                        const segments = visibleShiftSegments
                          .filter((segment) => segment.work_shift_id === shift.id)
                          .sort((a, b) => a.start_time.localeCompare(b.start_time));
                        const clickedMinute = minuteFromShiftPointer(shift, event);
                        const segment = segmentFromShiftMinute(segments, clickedMinute);
                        if (segment) {
                          return;
                        }
                        const gap = gapFromShiftMinute(shift, segments, clickedMinute);
                        if (!gap || isReadOnly || !selectedDate) {
                          return;
                        }
                        setEmptySlotMenu({
                          date: selectedDate,
                          endTime: gap.endTime,
                          left: Math.min(event.clientX, window.innerWidth - 220),
                          shift,
                          staff,
                          startTime: gap.startTime,
                          top: Math.min(event.clientY, window.innerHeight - 230)
                        });
                      }}
                      onContextMenu={(event) => {
                        const segments = visibleShiftSegments
                          .filter((segment) => segment.work_shift_id === shift.id)
                          .sort((a, b) => a.start_time.localeCompare(b.start_time));
                        const clickedMinute = minuteFromShiftPointer(shift, event);
                        const segment = segmentFromShiftMinute(segments, clickedMinute);
                        if (segment) {
                          openSegmentMenu(event, shift, segment, splitTimeFromMinute(segment, clickedMinute));
                          return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        const gap = gapFromShiftMinute(shift, segments, clickedMinute);
                        if (!gap || isReadOnly || !selectedDate) {
                          return;
                        }
                        setEmptySlotMenu({
                          date: selectedDate,
                          endTime: gap.endTime,
                          left: Math.min(event.clientX, window.innerWidth - 220),
                          shift,
                          staff,
                          startTime: gap.startTime,
                          top: Math.min(event.clientY, window.innerHeight - 230)
                        });
                      }}
                      style={{
                        left: `${percentFromTime(shift.start_time, timeline.startMinute, timeline.totalMinutes)}%`,
                        width: `${percentDuration(shift.start_time, shift.end_time, timeline.totalMinutes)}%`
                      }}
                      title={`${staff.employee_number ?? staff.display_name} ${shift.start_time.slice(0, 5)}-${shift.end_time.slice(0, 5)}`}
                    >
                      <span className="absolute -top-4 left-0 text-[10px] text-neutral-500">
                        {shift.start_time.slice(0, 5)}-{shift.end_time.slice(0, 5)}
                      </span>
                      <div className="relative h-full overflow-visible rounded">
                        {visibleShiftSegments
                          .filter((segment) => segment.work_shift_id === shift.id)
                          .sort((a, b) => a.start_time.localeCompare(b.start_time))
                          .map((segment, segmentIndex, shiftSegments) => (
                            <SegmentBlock
                              isFirstInShift={segmentIndex === 0}
                              isLastInShift={segmentIndex === shiftSegments.length - 1}
                              isHovered={hoveredSegmentId === segment.id}
                              isMergeSelected={mergeSelection.includes(segment.id)}
                              isReadOnly={isReadOnly}
                              isSelected={selection?.type === "shiftSegment" && selection.id === segment.id}
                              hasWarning={warningCountBySegment.has(segment.id)}
                              isWarningActive={activeWarningSegmentId === segment.id}
                              key={segment.id}
                              onHover={(id) => setHoveredSegment(id)}
                              onOpenMenu={(event) => openSegmentMenu(event, shift, segment)}
                              onResizeEdge={(side, nextTime) => {
                                const firstSegment = shiftSegments[0];
                                const lastSegment = shiftSegments[shiftSegments.length - 1];
                                if (side === "left" && segment.id === firstSegment?.id) {
                                  queueCommand({
                                    type: "ResizeWorkShift",
                                    payload: { work_shift_id: shift.id, start_time: nextTime, end_time: shift.end_time }
                                  });
                                  queueCommand({
                                    type: "ResizeSegment",
                                    payload: { segment_id: segment.id, start_time: nextTime }
                                  });
                                }
                                if (side === "right" && segment.id === lastSegment?.id) {
                                  queueCommand({
                                    type: "ResizeWorkShift",
                                    payload: { work_shift_id: shift.id, start_time: shift.start_time, end_time: nextTime }
                                  });
                                  queueCommand({
                                    type: "ResizeSegment",
                                    payload: { segment_id: segment.id, end_time: nextTime }
                                  });
                                }
                              }}
                              onSelect={() => {
                                selectShiftSegment(segment.id);
                                toggleMergeSelection(shift.id, segment);
                              }}
                              proposalMode={activeProposalSegmentIds[segment.id] ?? null}
                              segment={segment}
                              shift={shift}
                              timeline={timeline}
                              warningCount={warningCountBySegment.get(segment.id) ?? 0}
                              leftPercent={percentFromTimeInRange(
                                segment.start_time,
                                shift.start_time,
                                minutesBetween(shift.start_time, shift.end_time)
                              )}
                              widthPercent={percentDuration(
                                segment.start_time,
                                segment.end_time,
                                minutesBetween(shift.start_time, shift.end_time),
                                0.5
                              )}
                              workspace={draftWorkspace}
                            />
                          ))}
                      </div>
                      {shift.is_locked && <Lock className="absolute right-1 top-1 h-3.5 w-3.5 text-neutral-500" />}
                    </div>
                  ))}
                  {shifts.length === 0 && (
                    <EmptyStaffLane request={requestsByStaff.get(staff.id)} timeline={timeline} />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
      {segmentMenu && (
        <SegmentPositionMenu
          onClose={() => setSegmentMenu(null)}
          onSelect={(option) => {
            const command = commandForOption(segmentMenu.segment, option);
            if (command) {
              queueCommandWithAutoMerge(command, segmentMenu.segment.id);
              selectShiftSegment(segmentMenu.segment.id);
            }
            setSegmentMenu(null);
          }}
          options={segmentOptions(draftWorkspace, segmentMenu.shift, segmentMenu.segment)}
          position={{ left: segmentMenu.left, top: segmentMenu.top }}
          segment={segmentMenu.segment}
          splitTime={segmentMenu.splitTime}
          onSplit={(splitTime) => {
            queueCommand({
              type: "SplitSegment",
              payload: {
                segment_id: segmentMenu.segment.id,
                split_time: splitTime
              }
            });
            selectShiftSegment(segmentMenu.segment.id);
            setSegmentMenu(null);
          }}
          mergeTarget={segmentMenu.mergeTarget}
          onMerge={(target) => {
            const orderedSegments = [segmentMenu.segment, target.segment].sort((a, b) =>
              a.start_time.localeCompare(b.start_time)
            );
            queueCommand({
              type: "MergeSegment",
              payload: {
                first_segment_id: orderedSegments[0].id,
                second_segment_id: orderedSegments[1].id
              }
            });
            selectShiftSegment(orderedSegments[0].id);
            setSegmentMenu(null);
          }}
          onDelete={() => {
            queueCommand({
              type: "DeleteShiftSegment",
              payload: {
                segment_id: segmentMenu.segment.id
              }
            });
            clearMergeSelection();
            setSegmentMenu(null);
          }}
          onToggleLock={() => {
            queueCommand(
              segmentMenu.segment.is_locked
                ? {
                    type: "UnlockSegment",
                    payload: {
                      segment_id: segmentMenu.segment.id
                    }
                  }
                : {
                    type: "LockSegment",
                    payload: {
                      segment_id: segmentMenu.segment.id,
                      lock_scope: "full",
                      lock_reason: null
                    }
                  }
            );
            selectShiftSegment(segmentMenu.segment.id);
            setSegmentMenu(null);
          }}
        />
      )}
      {emptySlotMenu && (
        <EmptySlotMenu
          onClose={() => setEmptySlotMenu(null)}
          onSelect={(option) => {
            const command = commandForEmptySlot(draftWorkspace, emptySlotMenu, option);
            if (command) {
              queueCommand(command);
            }
            setEmptySlotMenu(null);
          }}
          options={emptySlotOptions(draftWorkspace, emptySlotMenu)}
          position={{ left: emptySlotMenu.left, top: emptySlotMenu.top }}
          slot={emptySlotMenu}
        />
      )}
    </section>
  );
}

type Timeline = ReturnType<typeof buildTimeline>;

const STAFF_COLUMN_WIDTH = 150;
const MIN_HOUR_WIDTH = 56;
const MAX_HOUR_WIDTH = 96;

type SegmentMenuState = {
  left: number;
  mergeTarget?: SegmentMergeTarget | null;
  segment: ShiftSegment;
  shift: WorkspaceData["work_shifts"][number];
  splitTime?: string | null;
  top: number;
};

type EmptySlotMenuState = {
  date: string;
  endTime: string;
  left: number;
  shift?: WorkspaceData["work_shifts"][number];
  staff: WorkspaceData["staff_members"][number];
  startTime: string;
  top: number;
};

type SegmentMergeTarget = {
  label: string;
  segment: ShiftSegment;
};


function EmptyStaffLane({
  request,
  timeline
}: {
  request?: WorkspaceData["shift_requests"][number];
  timeline: Timeline;
}) {
  if (!request) {
    return (
      <div className="flex h-full items-center px-3 text-xs text-neutral-400">
        希望入力後、AI提案で勤務ブロックが作成されます。
      </div>
    );
  }
  if (request.request_type === "off") {
    return (
      <div className="flex h-full items-center px-3 text-xs text-neutral-500">
        休み希望
      </div>
    );
  }
  if (!request.start_time || !request.end_time) {
    return (
      <div className="flex h-full items-center px-3 text-xs text-neutral-500">
        希望入力済み
      </div>
    );
  }
  return (
    <div
      className="pointer-events-none absolute top-5 h-14 rounded border border-dashed border-neutral-300 bg-neutral-50 px-2 py-1 text-xs text-neutral-500"
      style={{
        left: `${percentFromTime(request.start_time, timeline.startMinute, timeline.totalMinutes)}%`,
        width: `${percentDuration(request.start_time, request.end_time, timeline.totalMinutes)}%`
      }}
    >
      <div className="font-medium">希望</div>
      <div>
        {request.start_time.slice(0, 5)}-{request.end_time.slice(0, 5)}
      </div>
      <div className="mt-0.5 text-[10px]">AI未採用</div>
    </div>
  );
}

function formatDateWithWeekday(value: string) {
  const date = new Date(`${value}T00:00:00`);
  const weekdays = ["日", "月", "火", "水", "木", "金", "土"];
  return `${value.replaceAll("-", "/")}（${weekdays[date.getDay()]}）`;
}

function SegmentBlock({
  hasWarning,
  isFirstInShift,
  isLastInShift,
  isReadOnly,
  isSelected,
  isHovered,
  isMergeSelected,
  isWarningActive,
  leftPercent,
  onHover,
  onOpenMenu,
  onResizeEdge,
  onSelect,
  proposalMode,
  segment,
  shift,
  timeline,
  warningCount,
  widthPercent,
  workspace
}: {
  hasWarning: boolean;
  isFirstInShift: boolean;
  isLastInShift: boolean;
  isReadOnly: boolean;
  isSelected: boolean;
  isHovered: boolean;
  isMergeSelected: boolean;
  isWarningActive: boolean;
  leftPercent: number;
  onHover: (id: string | null) => void;
  onOpenMenu: (event: MouseEvent<HTMLElement>) => void;
  onResizeEdge: (side: "left" | "right", nextTime: string) => void;
  onSelect: () => void;
  proposalMode: "before" | "after" | "add" | "delete" | null;
  segment: ShiftSegment;
  shift: WorkspaceData["work_shifts"][number];
  timeline: Timeline;
  warningCount: number;
  widthPercent: number;
  workspace: WorkspaceData;
}) {
  const position = workspace.positions.find((item) => item.id === segment.position_id);
  const task = workspace.task_types.find((item) => item.id === segment.task_type_id);
  const label = segment.segment_type === "WORK" ? position?.code : segment.segment_type === "TASK" ? task?.code : "BREAK";
  const displayLabel = segment.segment_type === "WORK" && segment.label ? segment.label : label;
  const durationMinutes = minutesBetween(segment.start_time, segment.end_time);
  const isTiny = durationMinutes <= 15;
  const isCompact = durationMinutes <= 30;

  return (
    <span
      className={`${segmentClassName(segment, label, isSelected || isMergeSelected, isHovered, hasWarning, isWarningActive, proposalMode)} absolute top-1 bottom-1`}
      aria-haspopup="menu"
      data-segment-id={segment.id}
      onClick={(event) => {
        event.stopPropagation();
        onSelect();
      }}
      onContextMenu={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onSelect();
        if (!isReadOnly) {
          onOpenMenu(event);
        }
      }}
      onMouseEnter={() => onHover(segment.id)}
      onMouseLeave={() => onHover(null)}
      role="button"
      style={{ left: `${leftPercent}%`, width: `${widthPercent}%` }}
      tabIndex={0}
    >
      {!isReadOnly && !segment.is_locked && isFirstInShift && (
        <SegmentEdgeHandle
          side="left"
          onResize={(nextTime) => onResizeEdge("left", nextTime)}
          shift={shift}
          timeline={timeline}
        />
      )}
      <span className={`flex min-w-0 items-center gap-1 ${isTiny ? "justify-center" : ""}`}>
        <span className={isTiny ? "text-sm font-bold leading-none" : "truncate"}>
          {displayLabel ?? segment.segment_type}
        </span>
        {segment.is_locked && <Lock className="h-3 w-3 shrink-0" />}
        {warningCount > 0 && (
          <span className="inline-flex shrink-0 items-center gap-0.5 rounded bg-amber-200 px-1 text-[10px] text-amber-950">
            <TriangleAlert className="h-2.5 w-2.5" />
            {warningCount}
          </span>
        )}
        {proposalMode && (
          <span className={proposalBadgeClassName(proposalMode)}>{proposalLabel(proposalMode)}</span>
        )}
      </span>
      {!isCompact && (
        <span className="text-[10px] opacity-75">
          {segment.start_time.slice(0, 5)}-{segment.end_time.slice(0, 5)}
        </span>
      )}
      {!isReadOnly && !segment.is_locked && isLastInShift && (
        <SegmentEdgeHandle
          side="right"
          onResize={(nextTime) => onResizeEdge("right", nextTime)}
          shift={shift}
          timeline={timeline}
        />
      )}
    </span>
  );
}

function SegmentEdgeHandle({
  onResize,
  shift,
  side,
  timeline
}: {
  onResize: (nextTime: string) => void;
  shift: WorkspaceData["work_shifts"][number];
  side: "left" | "right";
  timeline: Timeline;
}) {
  return (
    <button
      aria-label={side === "left" ? "先頭セグメントの開始を変更" : "末尾セグメントの終了を変更"}
      className={`absolute top-0 z-30 h-full w-2 cursor-ew-resize bg-blue-600/0 hover:bg-blue-600/30 ${
        side === "left" ? "left-0 rounded-l" : "right-0 rounded-r"
      }`}
      draggable={false}
      onClick={(event) => event.stopPropagation()}
      onPointerDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
        const row = event.currentTarget.closest("[data-staff-id]");
        if (!(row instanceof HTMLElement)) {
          return;
        }
        const handleUp = (upEvent: PointerEvent) => {
          window.removeEventListener("pointerup", handleUp);
          const rawMinute = minuteFromClientX(upEvent.clientX, row, timeline);
          const snapped = snapMinute(rawMinute, timeline.startMinute, timeline.totalMinutes);
          const minMinute = timeToMinutes(shift.start_time);
          const maxMinute = timeToMinutes(shift.end_time);
          const nextMinute = side === "left"
            ? Math.min(snapped, maxMinute - 15)
            : Math.max(snapped, minMinute + 15);
          onResize(minuteToTime(nextMinute));
        };
        window.addEventListener("pointerup", handleUp);
      }}
      type="button"
    />
  );
}

function SegmentPositionMenu({
  mergeTarget,
  onClose,
  onDelete,
  onMerge,
  onSelect,
  onSplit,
  onToggleLock,
  options,
  position,
  segment,
  splitTime
}: {
  mergeTarget?: SegmentMergeTarget | null;
  onClose: () => void;
  onDelete: () => void;
  onMerge: (target: SegmentMergeTarget) => void;
  onSelect: (option: SegmentOption) => void;
  onSplit: (splitTime: string) => void;
  onToggleLock: () => void;
  options: SegmentOption[];
  position: { left: number; top: number };
  segment: ShiftSegment;
  splitTime?: string | null;
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(event) => {
          event.preventDefault();
          onClose();
        }}
        role="presentation"
      />
      <div
        className="fixed z-50 min-w-52 rounded border bg-white p-1 text-xs text-neutral-900 shadow-2xl"
        onMouseDown={(event) => event.preventDefault()}
        onPointerDown={(event) => event.stopPropagation()}
        role="menu"
        style={{ left: position.left, top: position.top }}
      >
        <div className="border-b border-neutral-400/50 pb-1">
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left font-medium hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400 disabled:hover:bg-white"
            disabled={!splitTime || segment.is_locked}
            onClick={(event) => {
              event.stopPropagation();
              if (splitTime) {
                onSplit(splitTime);
              }
            }}
            role="menuitem"
            title={segment.is_locked ? "ロック中は分割できません" : splitTime ? `${splitTime}で分割` : "セグメントの端では分割できません"}
            type="button"
          >
            <span>ここで分割</span>
            <span>{splitTime ?? "-"}</span>
          </button>
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left font-medium hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400 disabled:hover:bg-white"
            disabled={!mergeTarget || segment.is_locked}
            onClick={(event) => {
              event.stopPropagation();
              if (mergeTarget) {
                onMerge(mergeTarget);
              }
            }}
            role="menuitem"
            title={segment.is_locked ? "ロック中は結合できません" : mergeTarget ? `${mergeTarget.label}と結合` : "隣の同じポジション/休憩とだけ結合できます"}
            type="button"
          >
            <span>結合</span>
            <span>{mergeTarget?.label ?? "-"}</span>
          </button>
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:text-neutral-400 disabled:hover:bg-white"
            disabled={segment.is_locked}
            onClick={(event) => {
              event.stopPropagation();
              if (!segment.is_locked) {
                onDelete();
              }
            }}
            role="menuitem"
            type="button"
          >
            <span>削除</span>
            <span>Delete</span>
          </button>
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left font-medium hover:bg-neutral-100"
            onClick={(event) => {
              event.stopPropagation();
              onToggleLock();
            }}
            role="menuitem"
            type="button"
          >
            <span>{segment.is_locked ? "ロック解除" : "ロック"}</span>
            <span>{segment.is_locked ? "Unlock" : "Lock"}</span>
          </button>
        </div>
        <div className="px-3 pb-1 pt-2 text-[10px] font-semibold text-neutral-500">
          ポジション変更
        </div>
        {options.map((option) => (
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400 disabled:hover:bg-white"
            disabled={segment.is_locked || !option.enabled || option.isCurrent}
            key={option.code}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(option);
            }}
            role="menuitem"
            title={segment.is_locked ? "ロック中は変更できません" : option.reason}
            type="button"
          >
            <span>{option.label}</span>
            <span>{option.isCurrent ? "現在" : option.enabled ? "○" : "×"}</span>
          </button>
        ))}
        <div className="mt-1 border-t px-3 pt-1 text-[10px] text-neutral-500">
          {segment.start_time.slice(0, 5)}-{segment.end_time.slice(0, 5)}
        </div>
      </div>
    </>
  );
}

function EmptySlotMenu({
  onClose,
  onSelect,
  options,
  position,
  slot
}: {
  onClose: () => void;
  onSelect: (option: SegmentOption) => void;
  options: SegmentOption[];
  position: { left: number; top: number };
  slot: EmptySlotMenuState;
}) {
  return (
    <>
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
        onContextMenu={(event) => {
          event.preventDefault();
          onClose();
        }}
        role="presentation"
      />
      <div
        className="fixed z-50 min-w-56 rounded border bg-white p-1 text-xs text-neutral-900 shadow-2xl"
        onMouseDown={(event) => event.preventDefault()}
        role="menu"
        style={{ left: position.left, top: position.top }}
      >
        <div className="border-b px-3 py-2">
          <div className="font-semibold">{slot.staff.employee_number ?? staffDisplayName(slot.staff)}</div>
          <div className="text-neutral-500">
            {slot.startTime}-{slot.endTime}
          </div>
        </div>
        <div className="px-3 pb-1 pt-2 text-[10px] font-semibold text-neutral-500">
          空白に追加
        </div>
        {options.map((option) => (
          <button
            className="flex w-full items-center justify-between rounded px-3 py-1.5 text-left hover:bg-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-400 disabled:hover:bg-white"
            disabled={!option.enabled}
            key={option.code}
            onClick={(event) => {
              event.stopPropagation();
              onSelect(option);
            }}
            role="menuitem"
            title={option.reason}
            type="button"
          >
            <span>{option.label}</span>
            <span>{option.enabled ? "追加" : "×"}</span>
          </button>
        ))}
      </div>
    </>
  );
}

function countWarningsBySegment(workspace: WorkspaceData) {
  const counts = new Map<string, number>();
  for (const warning of workspace.warnings) {
    if (warning.shift_segment_id) {
      counts.set(warning.shift_segment_id, (counts.get(warning.shift_segment_id) ?? 0) + 1);
      continue;
    }
    if (warning.work_shift_id) {
      for (const segment of workspace.shift_segments) {
        if (segment.work_shift_id === warning.work_shift_id) {
          counts.set(segment.id, (counts.get(segment.id) ?? 0) + 1);
        }
      }
      continue;
    }
  }
  return counts;
}

function minuteFromShiftPointer(
  shift: WorkspaceData["work_shifts"][number],
  event: MouseEvent<HTMLElement>
) {
  const rect = event.currentTarget.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
  return timeToMinutes(shift.start_time) + ratio * minutesBetween(shift.start_time, shift.end_time);
}

function segmentFromShiftMinute(
  segments: ShiftSegment[],
  clickedMinute: number
) {
  if (segments.length === 0) {
    return null;
  }
  const matchingSegment = segments.find((segment) => {
    const start = timeToMinutes(segment.start_time);
    const end = timeToMinutes(segment.end_time);
    return clickedMinute >= start && clickedMinute < end;
  });
  if (matchingSegment) {
    return matchingSegment;
  }
  return null;
}

function gapFromShiftMinute(
  shift: WorkspaceData["work_shifts"][number],
  segments: ShiftSegment[],
  clickedMinute: number
) {
  const shiftStart = timeToMinutes(shift.start_time);
  const shiftEnd = timeToMinutes(shift.end_time);
  const sortedSegments = segments
    .filter((segment) => segment.work_shift_id === shift.id)
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  let cursor = shiftStart;
  for (const segment of sortedSegments) {
    const segmentStart = timeToMinutes(segment.start_time);
    const segmentEnd = timeToMinutes(segment.end_time);
    if (cursor < segmentStart && cursor <= clickedMinute && clickedMinute < segmentStart) {
      return {
        startTime: minuteToTime(cursor),
        endTime: minuteToTime(segmentStart)
      };
    }
    cursor = Math.max(cursor, segmentEnd);
  }
  if (cursor < shiftEnd && cursor <= clickedMinute && clickedMinute < shiftEnd) {
    return {
      startTime: minuteToTime(cursor),
      endTime: minuteToTime(shiftEnd)
    };
  }
  return null;
}

function splitTimeFromSegmentPointer(event: MouseEvent<HTMLElement>, segment: ShiftSegment) {
  const rect = event.currentTarget.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / Math.max(1, rect.width)));
  const minute = timeToMinutes(segment.start_time) + ratio * minutesBetween(segment.start_time, segment.end_time);
  return splitTimeFromMinute(segment, minute);
}

function splitTimeFromMinute(segment: ShiftSegment, minute: number) {
  const splitMinute = Math.round(minute / 15) * 15;
  if (
    splitMinute <= timeToMinutes(segment.start_time) ||
    splitMinute >= timeToMinutes(segment.end_time)
  ) {
    return null;
  }
  return minuteToTime(splitMinute);
}

function mergeTargetForSegment(segments: ShiftSegment[], segment: ShiftSegment): SegmentMergeTarget | null {
  if (segment.id.startsWith("draft-")) {
    return null;
  }
  const index = segments.findIndex((item) => item.id === segment.id);
  if (index < 0) {
    return null;
  }
  const next = segments[index + 1];
  if (next && !next.id.startsWith("draft-") && areSegmentsMergeable(segment, next)) {
    return { label: "次と結合", segment: next };
  }
  const previous = segments[index - 1];
  if (previous && !previous.id.startsWith("draft-") && areSegmentsMergeable(previous, segment)) {
    return { label: "前と結合", segment: previous };
  }
  return null;
}

function mergeCommandsForSelection(segments: ShiftSegment[], selectedIds: string[]): ScheduleCommand[] {
  if (selectedIds.length < 2) {
    return [];
  }
  const selected = selectedIds
    .map((id) => segments.find((segment) => segment.id === id))
    .filter((segment): segment is ShiftSegment => Boolean(segment))
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  if (selected.length < 2 || selected.some((segment) => segment.id.startsWith("draft-"))) {
    return [];
  }
  const workShiftId = selected[0]?.work_shift_id;
  if (!workShiftId || selected.some((segment) => segment.work_shift_id !== workShiftId)) {
    return [];
  }
  for (let index = 0; index < selected.length - 1; index += 1) {
    if (!areSegmentsMergeable(selected[index], selected[index + 1])) {
      return [];
    }
  }
  const anchorId = selected[0].id;
  return selected.slice(1).map((segment) => ({
    type: "MergeSegment",
    payload: {
      first_segment_id: anchorId,
      second_segment_id: segment.id
    }
  }));
}

function mergeAnchorSegmentId(segments: ShiftSegment[], selectedIds: string[]) {
  const selected = selectedIds
    .map((id) => segments.find((segment) => segment.id === id))
    .filter((segment): segment is ShiftSegment => Boolean(segment))
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  return selected[0]?.id ?? null;
}

function areSegmentsMergeable(first: ShiftSegment, second: ShiftSegment) {
  return (
    first.work_shift_id === second.work_shift_id &&
    first.end_time === second.start_time &&
    first.segment_type === second.segment_type &&
    first.position_id === second.position_id &&
    first.task_type_id === second.task_type_id
  );
}

export function autoMergeCommandsAfterCommand(
  workspace: WorkspaceData,
  pendingCommands: ScheduleCommand[],
  workShiftDrafts: Record<string, Partial<WorkspaceData["work_shifts"][number]>>,
  command: ScheduleCommand,
  affectedSegmentId?: string
): ScheduleCommand[] {
  if (!affectedSegmentId || affectedSegmentId.startsWith("draft-")) {
    return [];
  }
  if (
    ![
      "UpdateSegmentPosition",
      "UpdateSegmentTask",
      "UpdateSegmentBreak",
      "ResizeSegment"
    ].includes(command.type)
  ) {
    return [];
  }
  const preview = applyDraftCommands(workspace, [...pendingCommands, command], workShiftDrafts);
  const target = preview.shift_segments.find((segment) => segment.id === affectedSegmentId);
  if (!target || target.id.startsWith("draft-")) {
    return [];
  }
  const shiftSegments = preview.shift_segments
    .filter((segment) => segment.work_shift_id === target.work_shift_id)
    .sort((first, second) => first.start_time.localeCompare(second.start_time));
  const targetIndex = shiftSegments.findIndex((segment) => segment.id === target.id);
  if (targetIndex < 0) {
    return [];
  }

  let firstIndex = targetIndex;
  while (
    firstIndex > 0 &&
    !shiftSegments[firstIndex - 1].id.startsWith("draft-") &&
    areSegmentsMergeable(shiftSegments[firstIndex - 1], shiftSegments[firstIndex])
  ) {
    firstIndex -= 1;
  }

  let lastIndex = targetIndex;
  while (
    lastIndex < shiftSegments.length - 1 &&
    !shiftSegments[lastIndex + 1].id.startsWith("draft-") &&
    areSegmentsMergeable(shiftSegments[lastIndex], shiftSegments[lastIndex + 1])
  ) {
    lastIndex += 1;
  }

  const mergeGroup = shiftSegments.slice(firstIndex, lastIndex + 1);
  if (mergeGroup.length < 2 || mergeGroup.some((segment) => segment.id.startsWith("draft-"))) {
    return [];
  }

  const anchor = mergeGroup[0];
  return mergeGroup.slice(1).map((segment) => ({
    type: "MergeSegment",
    payload: {
      first_segment_id: anchor.id,
      second_segment_id: segment.id
    }
  }));
}

type SegmentOption = {
  assignmentLabel?: "SH" | "ST";
  code: "B" | "SH" | "ST" | "C" | "F" | "S" | "M" | "BREAK";
  enabled: boolean;
  id?: string;
  isCurrent: boolean;
  label: string;
  reason: string;
  type: "position" | "task" | "break";
};

function segmentOptions(
  workspace: WorkspaceData,
  shift: WorkspaceData["work_shifts"][number],
  segment: ShiftSegment
): SegmentOption[] {
  const staffSkillIds = new Set(
    workspace.staff_skills
      .filter((skill) => skill.staff_member_id === shift.staff_member_id)
      .map((skill) => skill.skill_definition_id)
  );
  const positionOptions: SegmentOption[] = (["B", "C", "F", "S"] as const).map((code) => {
    const position = workspace.positions.find((item) => item.code === code);
    const skill = workspace.skill_definitions.find(
      (item) => item.code === code && item.skill_category === "position"
    );
    const hasSkill = Boolean(skill && staffSkillIds.has(skill.id));
    return {
      code,
      enabled: Boolean(position && hasSkill),
      id: position?.id,
      isCurrent:
        segment.segment_type === "WORK"
        && segment.position_id === position?.id
        && (code !== "B" || !["SH", "ST"].includes(segment.label ?? "")),
      label: positionDisplayLabel(code, position?.name),
      reason: !position ? "ポジション未設定" : hasSkill ? `${code}スキルあり` : `${code}スキルなし`,
      type: "position"
    };
  });
  const bPosition = workspace.positions.find((item) => item.code === "B");
  const bSkill = workspace.skill_definitions.find(
    (item) => item.code === "B" && item.skill_category === "position"
  );
  const hasB = Boolean(bSkill && staffSkillIds.has(bSkill.id));
  const laneOptions: SegmentOption[] = (["SH", "ST"] as const).map((label) => ({
    assignmentLabel: label,
    code: label,
    enabled: Boolean(bPosition && hasB),
    id: bPosition?.id,
    isCurrent:
      segment.segment_type === "WORK"
      && segment.position_id === bPosition?.id
      && segment.label === label,
    label: `${label} / ${label === "SH" ? "ショット" : "スチーム"}`,
    reason: hasB ? `B / バリの${label}担当` : "B / バリスキルなし",
    type: "position"
  }));
  const taskM = workspace.task_types.find((item) => item.code === "M");
  const mSkill = workspace.skill_definitions.find(
    (item) => item.code === "M" && item.skill_category === "task"
  );
  const hasM = Boolean(mSkill && staffSkillIds.has(mSkill.id));
  const mTimeValid = isValidDepositManualWindow(workspace, shift, segment);
  const mOption: SegmentOption = {
    code: "M",
    enabled: Boolean(taskM && hasM && mTimeValid),
    id: taskM?.id,
    isCurrent: segment.segment_type === "TASK" && segment.task_type_id === taskM?.id,
    label: positionDisplayLabel("M", taskM?.name),
    reason: !taskM
      ? "Mタスク未設定"
      : !hasM
        ? "Mスキルなし"
        : mTimeValid
          ? "Mスキルあり"
          : "Mは10:00-10:30または前日クローズ30分のみ",
    type: "task"
  };
  return [
    ...positionOptions.slice(0, 1),
    ...laneOptions,
    ...positionOptions.slice(1),
    mOption,
    {
      code: "BREAK",
      enabled: true,
      isCurrent: segment.segment_type === "BREAK",
      label: "BREAK / 休憩",
      reason: "休憩",
      type: "break"
    }
  ];
}

function emptySlotOptions(
  workspace: WorkspaceData,
  slot: EmptySlotMenuState
): SegmentOption[] {
  const staffSkillIds = new Set(
    workspace.staff_skills
      .filter((skill) => skill.staff_member_id === slot.staff.id)
      .map((skill) => skill.skill_definition_id)
  );
  const positionOptions: SegmentOption[] = (["B", "C", "F", "S"] as const).map((code) => {
    const position = workspace.positions.find((item) => item.code === code);
    const skill = workspace.skill_definitions.find(
      (item) => item.code === code && item.skill_category === "position"
    );
    const hasSkill = Boolean(skill && staffSkillIds.has(skill.id));
    return {
      code,
      enabled: Boolean(position && hasSkill),
      id: position?.id,
      isCurrent: false,
      label: positionDisplayLabel(code, position?.name),
      reason: !position ? "ポジション未設定" : hasSkill ? `${code}スキルあり` : `${code}スキルなし`,
      type: "position"
    };
  });
  const taskM = workspace.task_types.find((item) => item.code === "M");
  const mSkill = workspace.skill_definitions.find(
    (item) => item.code === "M" && item.skill_category === "task"
  );
  const hasM = Boolean(mSkill && staffSkillIds.has(mSkill.id));
  const mTimeValid = slot.startTime === "10:00" || isClosingRescueSlot(workspace, slot.date, slot.startTime);
  const mOption: SegmentOption = {
    code: "M",
    enabled: Boolean(taskM && hasM && mTimeValid),
    id: taskM?.id,
    isCurrent: false,
    label: positionDisplayLabel("M", taskM?.name),
    reason: !taskM
      ? "Mタスク未設定"
      : !hasM
        ? "Mスキルなし"
        : mTimeValid
          ? "Mスキルあり"
          : "Mは10:00またはクローズ30分枠のみ",
    type: "task"
  };
  return [
    ...positionOptions,
    mOption,
    {
      code: "BREAK",
      enabled: false,
      isCurrent: false,
      label: "BREAK / 休憩",
      reason: "休憩は既存勤務内のセグメントで追加します",
      type: "break"
    }
  ];
}

function commandForEmptySlot(
  workspace: WorkspaceData,
  slot: EmptySlotMenuState,
  option: SegmentOption
): ScheduleCommand | null {
  if (!option.enabled || !option.id) {
    return null;
  }
  const startTime = option.code === "M" ? normalizedDepositStart(workspace, slot.date, slot.startTime) : slot.startTime;
  const endTime = option.code === "M" ? minuteToTime(timeToMinutes(startTime) + 30) : slot.endTime;
  if (option.type === "position") {
    if (slot.shift) {
      return {
        type: "CreateWorkSegment",
        payload: {
          work_shift_id: slot.shift.id,
          start_time: startTime,
          end_time: endTime,
          position_id: option.id
        }
      };
    }
    return {
      type: "CreateWorkShift",
      payload: {
        staff_member_id: slot.staff.id,
        work_date: slot.date,
        start_time: startTime,
        end_time: endTime,
        position_id: option.id
      }
    };
  }
  if (option.type === "task") {
    if (slot.shift) {
      return {
        type: "CreateTaskSegment",
        payload: {
          work_shift_id: slot.shift.id,
          start_time: startTime,
          end_time: endTime,
          task_type_id: option.id
        }
      };
    }
    return {
      type: "CreateWorkShift",
      payload: {
        staff_member_id: slot.staff.id,
        work_date: slot.date,
        start_time: startTime,
        end_time: endTime,
        task_type_id: option.id
      }
    };
  }
  return null;
}

function commandForOption(segment: ShiftSegment, option: SegmentOption): ScheduleCommand | null {
  if (option.isCurrent || !option.enabled) {
    return null;
  }
  if (option.type === "position" && option.id) {
    return {
      type: "UpdateSegmentPosition",
      payload: {
        segment_id: segment.id,
        position_id: option.id,
        label: option.assignmentLabel ?? null
      }
    };
  }
  if (option.type === "task" && option.id) {
    return {
      type: "UpdateSegmentTask",
      payload: {
        segment_id: segment.id,
        task_type_id: option.id
      }
    };
  }
  if (option.type === "break") {
    return {
      type: "UpdateSegmentBreak",
      payload: {
        segment_id: segment.id
      }
    };
  }
  return null;
}

function normalizedDepositStart(workspace: WorkspaceData, date: string, startTime: string) {
  if (startTime === "10:00") {
    return startTime;
  }
  if (isClosingRescueSlot(workspace, date, startTime)) {
    return startTime;
  }
  return "10:00";
}

function isClosingRescueSlot(workspace: WorkspaceData, workDate: string, startTime: string) {
  const close = closingTimeForDate(workspace, workDate);
  return timeToMinutes(startTime) === timeToMinutes(close) - 30;
}

function isValidDepositManualWindow(
  workspace: WorkspaceData,
  shift: WorkspaceData["work_shifts"][number],
  segment: ShiftSegment
) {
  if (segment.start_time.slice(0, 5) === "10:00" && segment.end_time.slice(0, 5) === "10:30") {
    return true;
  }
  const close = closingTimeForDate(workspace, shift.work_date);
  const closeMinute = timeToMinutes(close);
  return (
    timeToMinutes(segment.start_time) === closeMinute - 30
    && timeToMinutes(segment.end_time) === closeMinute
  );
}

function closingTimeForDate(workspace: WorkspaceData, workDate: string) {
  const day = new Date(`${workDate}T00:00:00`).getDay();
  const dayType = day === 0 || day === 6 ? "holiday" : "weekday";
  const businessHours = workspace.store.business_hours as
    | Record<string, { close?: string; closing_time?: string }>
    | null;
  return (
    businessHours?.[dayType]?.close
    ?? businessHours?.[dayType]?.closing_time
    ?? workspace.store.closing_time
  );
}

function segmentClassName(
  segment: ShiftSegment,
  label: string | undefined,
  isSelected: boolean,
  isHovered: boolean,
  hasWarning: boolean,
  isWarningActive: boolean,
  proposalMode: "before" | "after" | "add" | "delete" | null
) {
  const selected = isSelected ? " ring-2 ring-blue-500 ring-offset-1" : "";
  const hovered = isHovered ? " brightness-95" : "";
  const warning = isWarningActive
    ? " ring-2 ring-amber-500 ring-offset-1"
    : hasWarning
      ? " border-amber-400 bg-amber-50 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.45)]"
      : "";
  const proposal = proposalMode ? proposalClassName(proposalMode) : "";
  const base = `flex min-w-0 flex-col justify-center overflow-hidden rounded border px-1.5 text-left text-[11px] transition${selected}${hovered}`;
  const color = segmentColorClassName(segment, label);
  return `${base} ${color}${warning}${proposal}`;
}

function segmentColorClassName(segment: ShiftSegment, label: string | undefined) {
  if (segment.segment_type === "BREAK") {
    return "border-neutral-300 bg-neutral-100 text-neutral-700";
  }
  if (segment.segment_type === "TASK" || label === "M") {
    return "border-amber-300 bg-amber-50 text-amber-900 shadow-[inset_3px_0_0_rgba(245,158,11,0.75)]";
  }
  const colors: Record<string, string> = {
    B: "border-sky-300 bg-sky-50 text-sky-950 shadow-[inset_3px_0_0_rgba(14,165,233,0.75)]",
    C: "border-emerald-300 bg-emerald-50 text-emerald-950 shadow-[inset_3px_0_0_rgba(16,185,129,0.75)]",
    F: "border-violet-300 bg-violet-50 text-violet-950 shadow-[inset_3px_0_0_rgba(139,92,246,0.75)]",
    S: "border-rose-300 bg-rose-50 text-rose-950 shadow-[inset_3px_0_0_rgba(244,63,94,0.75)]"
  };
  return colors[label ?? ""] ?? "border-sky-200 bg-sky-50 text-sky-900";
}

function proposalClassName(mode: "before" | "after" | "add" | "delete") {
  if (mode === "before") {
    return " border-red-300 bg-red-50 opacity-70";
  }
  if (mode === "after") {
    return " border-emerald-400 bg-emerald-50 ring-2 ring-emerald-300 ring-offset-1 opacity-80";
  }
  if (mode === "add") {
    return " border-blue-400 bg-blue-50 ring-2 ring-blue-300 ring-offset-1 opacity-80";
  }
  return " border-neutral-400 bg-neutral-50 opacity-50 line-through";
}

function proposalBadgeClassName(mode: "before" | "after" | "add" | "delete") {
  if (mode === "before") {
    return "rounded bg-red-200 px-1 text-[10px] text-red-950";
  }
  if (mode === "after") {
    return "rounded bg-emerald-200 px-1 text-[10px] text-emerald-950";
  }
  if (mode === "add") {
    return "rounded bg-blue-200 px-1 text-[10px] text-blue-950";
  }
  return "rounded bg-neutral-200 px-1 text-[10px] text-neutral-950";
}

function proposalLabel(mode: "before" | "after" | "add" | "delete") {
  return mode === "before" ? "前" : mode === "after" ? "後" : mode === "add" ? "追加" : "削除";
}

function groupShiftsByStaff(workspace: WorkspaceData) {
  const grouped = new Map<string, typeof workspace.work_shifts>();
  for (const shift of workspace.work_shifts) {
    const items = grouped.get(shift.staff_member_id) ?? [];
    items.push(shift);
    grouped.set(shift.staff_member_id, items);
  }
  for (const shifts of grouped.values()) {
    shifts.sort((a, b) => a.start_time.localeCompare(b.start_time));
  }
  return grouped;
}

function orderStaffForShiftGrid(
  staffMembers: WorkspaceData["staff_members"],
  shiftsByStaff: Map<string, WorkspaceData["work_shifts"]>
) {
  return [...staffMembers].sort((firstStaff, secondStaff) => {
    const firstShift = shiftsByStaff.get(firstStaff.id)?.[0];
    const secondShift = shiftsByStaff.get(secondStaff.id)?.[0];
    if (firstShift && secondShift) {
      const startCompare = firstShift.start_time.localeCompare(secondShift.start_time);
      if (startCompare !== 0) {
        return startCompare;
      }
      return compareStaffLabel(firstStaff, secondStaff);
    }
    if (firstShift || secondShift) {
      return firstShift ? -1 : 1;
    }
    return compareStaffLabel(firstStaff, secondStaff);
  });
}

function compareStaffLabel(
  firstStaff: WorkspaceData["staff_members"][number],
  secondStaff: WorkspaceData["staff_members"][number]
) {
  return staffSortLabel(firstStaff).localeCompare(staffSortLabel(secondStaff), "ja", {
    numeric: true
  });
}

function staffSortLabel(staff: WorkspaceData["staff_members"][number]) {
  return staff.employee_number || staff.display_name || staff.id;
}

function groupRequestsByStaff(workspace: WorkspaceData, selectedDate?: string) {
  const grouped = new Map<string, WorkspaceData["shift_requests"][number]>();
  for (const request of workspace.shift_requests) {
    if (selectedDate && request.request_date !== selectedDate) {
      continue;
    }
    grouped.set(request.staff_member_id, request);
  }
  return grouped;
}

function staffDisplayName(staff: WorkspaceData["staff_members"][number]) {
  if (staff.display_name && !/^新規スタッフ\d+$/.test(staff.display_name.trim())) {
    return staff.display_name;
  }
  return "";
}

function buildTimeline(workspace: WorkspaceData) {
  const times = [
    workspace.store.opening_time,
    workspace.store.closing_time,
    ...workspace.work_shifts.flatMap((shift) => [shift.start_time, shift.end_time]),
    ...workspace.shift_requests.flatMap((request) =>
      request.start_time && request.end_time ? [request.start_time, request.end_time] : []
    )
  ];
  const startHour = Math.floor(Math.min(...times.map(timeToMinutes)) / 60);
  const endHour = Math.ceil(Math.max(...times.map(timeToMinutes)) / 60);
  const hours = Array.from({ length: Math.max(1, endHour - startHour) }, (_, index) => (startHour + index) * 60);
  return {
    hours,
    startMinute: startHour * 60,
    totalMinutes: Math.max(60, (endHour - startHour) * 60)
  };
}

function responsiveHourWidth(hourCount: number, viewportWidth: number) {
  if (hourCount <= 0 || viewportWidth <= STAFF_COLUMN_WIDTH) {
    return MAX_HOUR_WIDTH;
  }
  const availableTimelineWidth = viewportWidth - STAFF_COLUMN_WIDTH;
  const fittedWidth = Math.floor(availableTimelineWidth / hourCount);
  return Math.max(MIN_HOUR_WIDTH, Math.min(MAX_HOUR_WIDTH, fittedWidth));
}

function formatHour(minutes: number) {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:00`;
}

function percentFromTime(value: string, startMinute: number, totalMinutes: number) {
  return ((timeToMinutes(value) - startMinute) / totalMinutes) * 100;
}

function percentFromTimeInRange(value: string, rangeStart: string, totalMinutes: number) {
  return ((timeToMinutes(value) - timeToMinutes(rangeStart)) / totalMinutes) * 100;
}

function percentDuration(start: string, end: string, totalMinutes: number, minimumPercent = 3) {
  return Math.max(minimumPercent, (minutesBetween(start, end) / totalMinutes) * 100);
}

function minutesBetween(start: string, end: string) {
  return timeToMinutes(end) - timeToMinutes(start);
}

function timeToMinutes(value: string) {
  const [hour, minute] = value.slice(0, 5).split(":").map(Number);
  return hour * 60 + minute;
}

function minuteToTime(value: number) {
  const clamped = Math.max(0, Math.min(23 * 60 + 59, Math.round(value)));
  const hour = Math.floor(clamped / 60);
  const minute = clamped % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function snapMinute(value: number, startMinute: number, totalMinutes: number) {
  const min = startMinute;
  const max = startMinute + totalMinutes;
  return Math.min(max, Math.max(min, Math.round(value / 15) * 15));
}

function minuteFromClientX(clientX: number, element: HTMLElement, timeline: Timeline) {
  const rect = element.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  return timeline.startMinute + ratio * timeline.totalMinutes;
}

export function applyDraftCommands(
  workspace: WorkspaceData,
  pendingCommands: ScheduleCommand[],
  workShiftDrafts: Record<string, Partial<WorkspaceData["work_shifts"][number]>>
): WorkspaceData {
  const workShifts = workspace.work_shifts.map((shift) => ({
    ...shift,
    ...(workShiftDrafts[shift.id] ?? {})
  }));
  const shiftSegments = workspace.shift_segments.map((segment) => {
    const originalShift = workspace.work_shifts.find((shift) => shift.id === segment.work_shift_id);
    const draft = workShiftDrafts[segment.work_shift_id];
    if (
      originalShift &&
      draft?.start_time &&
      draft?.end_time &&
      minutesBetween(originalShift.start_time, originalShift.end_time) === minutesBetween(draft.start_time, draft.end_time)
    ) {
      const delta = timeToMinutes(draft.start_time) - timeToMinutes(originalShift.start_time);
      return {
        ...segment,
        start_time: minuteToTime(timeToMinutes(segment.start_time) + delta),
        end_time: minuteToTime(timeToMinutes(segment.end_time) + delta)
      };
    }
    return { ...segment };
  });

  for (const command of pendingCommands) {
    if (command.type === "AssignStaff") {
      const shift = workShifts.find((item) => item.id === command.payload.work_shift_id);
      if (shift) {
        shift.staff_member_id = command.payload.staff_member_id;
      }
    }
    if (command.type === "ResizeWorkShift") {
      const shift = workShifts.find((item) => item.id === command.payload.work_shift_id);
      if (shift) {
        shift.start_time = command.payload.start_time;
        shift.end_time = command.payload.end_time;
        shift.total_work_minutes = minutesBetween(command.payload.start_time, command.payload.end_time);
      }
    }
    if (command.type === "DeleteWorkShift") {
      const index = workShifts.findIndex((item) => item.id === command.payload.work_shift_id);
      if (index >= 0) {
        workShifts.splice(index, 1);
      }
    }
    if (command.type === "DeleteShiftSegment") {
      const segmentIndex = shiftSegments.findIndex((item) => item.id === command.payload.segment_id);
      if (segmentIndex >= 0) {
        shiftSegments.splice(segmentIndex, 1);
      }
    }
    if (command.type === "CreateWorkShift") {
      const id = `draft-${workShifts.length}-${command.payload.staff_member_id}`;
      workShifts.push({
        id,
        schedule_version_id: workspace.current_schedule_version?.id ?? "draft",
        staff_member_id: command.payload.staff_member_id,
        store_id: workspace.store.id,
        work_date: command.payload.work_date,
        start_time: command.payload.start_time,
        end_time: command.payload.end_time,
        total_work_minutes: minutesBetween(command.payload.start_time, command.payload.end_time),
        total_break_minutes: 0,
        assignment_source: "manual",
        is_locked: false,
        lock_scope: null,
        locked_at: null,
        lock_reason: null,
        note: "未保存"
      });
      const payloadSegments = command.payload.segments?.length
        ? command.payload.segments
        : [
            {
              start_time: command.payload.start_time,
              end_time: command.payload.end_time,
              segment_type: command.payload.task_type_id ? ("TASK" as const) : ("WORK" as const),
              position_id: command.payload.position_id ?? null,
              task_type_id: command.payload.task_type_id ?? null
            }
          ];
      payloadSegments.forEach((payloadSegment, segmentIndex) => {
        shiftSegments.push({
          id: `${id}-segment-${segmentIndex}`,
          work_shift_id: id,
          schedule_version_id: workspace.current_schedule_version?.id ?? "draft",
          store_id: workspace.store.id,
          segment_date: command.payload.work_date,
          start_time: payloadSegment.start_time,
          end_time: payloadSegment.end_time,
          segment_type: payloadSegment.segment_type,
          position_id: payloadSegment.position_id ?? null,
          task_type_id: payloadSegment.task_type_id ?? null,
          label: "未保存",
          assignment_source: "manual",
          is_locked: false,
          lock_scope: null,
          locked_at: null,
          lock_reason: null,
          confidence_score: null,
          note: "未保存"
        });
      });
    }
    if (command.type === "CreateWorkSegment") {
      const shift = workShifts.find((item) => item.id === command.payload.work_shift_id);
      if (shift) {
        shiftSegments.push({
          id: `draft-work-segment-${command.payload.work_shift_id}-${command.payload.start_time}`,
          work_shift_id: command.payload.work_shift_id,
          schedule_version_id: workspace.current_schedule_version?.id ?? "draft",
          store_id: workspace.store.id,
          segment_date: shift.work_date,
          start_time: command.payload.start_time,
          end_time: command.payload.end_time,
          segment_type: "WORK",
          position_id: command.payload.position_id,
          task_type_id: null,
          label: "未保存",
          assignment_source: "manual",
          is_locked: false,
          lock_scope: null,
          locked_at: null,
          lock_reason: null,
          confidence_score: null,
          note: "未保存"
        });
      }
    }
    if (command.type === "CreateTaskSegment") {
      const shift = workShifts.find((item) => item.id === command.payload.work_shift_id);
      if (shift) {
        shiftSegments.push({
          id: `draft-task-segment-${command.payload.work_shift_id}-${command.payload.start_time}`,
          work_shift_id: command.payload.work_shift_id,
          schedule_version_id: workspace.current_schedule_version?.id ?? "draft",
          store_id: workspace.store.id,
          segment_date: shift.work_date,
          start_time: command.payload.start_time,
          end_time: command.payload.end_time,
          segment_type: "TASK",
          position_id: null,
          task_type_id: command.payload.task_type_id,
          label: "未保存",
          assignment_source: "manual",
          is_locked: false,
          lock_scope: null,
          locked_at: null,
          lock_reason: null,
          confidence_score: null,
          note: "未保存"
        });
      }
    }
    if (command.type === "SplitSegment") {
      const segmentIndex = shiftSegments.findIndex((item) => item.id === command.payload.segment_id);
      const segment = shiftSegments[segmentIndex];
      if (segment) {
        const splitMinute = timeToMinutes(command.payload.split_time);
        if (
          splitMinute > timeToMinutes(segment.start_time) &&
          splitMinute < timeToMinutes(segment.end_time)
        ) {
          const firstSegment = {
            ...segment,
            end_time: command.payload.split_time
          };
          const secondSegment = {
            ...segment,
            id: `draft-split-${segment.id}-${command.payload.split_time}`,
            start_time: command.payload.split_time
          };
          shiftSegments.splice(segmentIndex, 1, firstSegment, secondSegment);
        }
      }
    }
    if (command.type === "MergeSegment") {
      const firstIndex = shiftSegments.findIndex((item) => item.id === command.payload.first_segment_id);
      const secondIndex = shiftSegments.findIndex((item) => item.id === command.payload.second_segment_id);
      if (firstIndex >= 0 && secondIndex >= 0) {
        const ordered = [shiftSegments[firstIndex], shiftSegments[secondIndex]].sort((a, b) =>
          a.start_time.localeCompare(b.start_time)
        );
        if (areSegmentsMergeable(ordered[0], ordered[1])) {
          const mergedSegment = {
            ...ordered[0],
            end_time: ordered[1].end_time
          };
          const removeIds = new Set([ordered[0].id, ordered[1].id]);
          const insertIndex = Math.min(firstIndex, secondIndex);
          const remainingSegments = shiftSegments.filter((item) => !removeIds.has(item.id));
          remainingSegments.splice(insertIndex, 0, mergedSegment);
          shiftSegments.splice(0, shiftSegments.length, ...remainingSegments);
        }
      }
    }
    if (command.type === "ResizeSegment") {
      const segment = shiftSegments.find((item) => item.id === command.payload.segment_id);
      if (segment) {
        if (command.payload.start_time) {
          segment.start_time = command.payload.start_time;
        }
        if (command.payload.end_time) {
          segment.end_time = command.payload.end_time;
        }
      }
    }
    if (command.type === "UpdateSegmentPosition") {
      const segment = shiftSegments.find((item) => item.id === command.payload.segment_id);
      if (segment) {
        segment.segment_type = "WORK";
        segment.position_id = command.payload.position_id;
        segment.task_type_id = null;
        segment.label = command.payload.label ?? null;
      }
    }
    if (command.type === "UpdateSegmentTask") {
      const segment = shiftSegments.find((item) => item.id === command.payload.segment_id);
      if (segment) {
        segment.segment_type = "TASK";
        segment.position_id = null;
        segment.task_type_id = command.payload.task_type_id;
        segment.label = null;
      }
    }
    if (command.type === "UpdateSegmentBreak") {
      const segment = shiftSegments.find((item) => item.id === command.payload.segment_id);
      if (segment) {
        segment.segment_type = "BREAK";
        segment.position_id = null;
        segment.task_type_id = null;
        segment.label = null;
      }
    }
  }

  return {
    ...workspace,
    work_shifts: workShifts,
    shift_segments: shiftSegments
  };
}
