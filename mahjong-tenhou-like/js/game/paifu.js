const paifuIndexKey = "mahjongPaifuIndex";
const paifuCounterKey = "mahjongPaifuCounter";
const maxStoredPaifu = 120;

function startPaifuGame() {
  const nextNo = Number(localStorage.getItem(paifuCounterKey) || "0") + 1;
  localStorage.setItem(paifuCounterKey, String(nextNo));
  state.paifuTrialNo = nextNo;
  state.currentPaifu = {
    no: nextNo,
    startedAt: new Date().toISOString(),
    rules: { ...state.rules },
    rounds: [],
    result: null,
  };
  saveCurrentPaifu();
}

function startPaifuRound() {
  if (!state.currentPaifu) startPaifuGame();
  state.currentPaifu.rounds.push({
    label: `${roundWind()}${state.round}局`,
    roundWind: roundWind(),
    round: state.round,
    honba: state.honba,
    dealer: players[state.dealerIndex],
    scoresStart: { ...state.scores },
    doraIndicator: compactTile(state.doraIndicator),
    startingHands: Object.fromEntries(players.map((player) => [player, state.hands[player].map(compactTile)])),
    events: [],
    snapshots: [compactPaifuSnapshot("配牌")],
    outcome: null,
  });
  saveCurrentPaifu();
}

function recordPaifuEvent(type, data = {}) {
  const round = currentPaifuRound();
  if (!round) return;
  const event = compactPaifuEvent(type, data);
  round.events.push(event);
  round.snapshots ??= [];
  round.snapshots.push(compactPaifuSnapshot(paifuEventLabel(event)));
  if (round.events.length % 16 === 0) saveCurrentPaifu();
}

function finishPaifuRound(outcome) {
  const round = currentPaifuRound();
  if (!round) return;
  round.outcome = outcome;
  round.scoresEnd = { ...state.scores };
  saveCurrentPaifu();
}

function finishPaifuGame(result) {
  if (!state.currentPaifu) return;
  state.currentPaifu.finishedAt = new Date().toISOString();
  state.currentPaifu.result = result;
  saveCurrentPaifu();
}

function currentPaifuRound() {
  const rounds = state.currentPaifu?.rounds;
  return rounds?.[rounds.length - 1] ?? null;
}

function compactPaifuEvent(type, data) {
  if (type === "decision") {
    return {
      type,
      player: data.player ?? null,
      action: data.action ?? "",
      tile: compactTile(data.tile),
      reason: data.reason ?? "",
      score: Number.isFinite(data.score) ? Number(data.score.toFixed(1)) : null,
      shanten: Number.isFinite(data.shanten) ? data.shanten : null,
      waits: data.waits ?? null,
      alternatives: (data.alternatives ?? []).slice(0, 5).map((item) => ({
        tile: compactTile(item.tile),
        score: Number.isFinite(item.score) ? Number(item.score.toFixed(1)) : null,
        shanten: Number.isFinite(item.shanten) ? item.shanten : null,
        reason: item.reason ?? "",
      })),
    };
  }
  return {
    type,
    player: data.player ?? null,
    fromPlayer: data.fromPlayer ?? null,
    tile: compactTile(data.tile),
    sideways: Boolean(data.sideways),
  };
}

function compactPaifuSnapshot(label = "") {
  return {
    label,
    current: state.current,
    wallCount: state.wall.length,
    scores: { ...state.scores },
    hands: Object.fromEntries(players.map((player) => [player, state.hands[player].map(compactTile)])),
    rivers: Object.fromEntries(players.map((player) => [player, state.rivers[player].map((entry) => ({
      tile: compactTile(entry.tile),
      sideways: Boolean(entry.sideways),
    }))])),
    melds: Object.fromEntries(players.map((player) => [player, state.melds[player].map((meld) => ({
      type: meld.type,
      fromPlayer: meld.fromPlayer,
      claimedIndex: meld.claimedIndex,
      tiles: meld.tiles.map(compactTile),
    }))])),
  };
}

function paifuEventLabel(event) {
  const name = event.player ? playerSeatLabel(event.player) : "";
  const tile = event.tile?.mark ?? "";
  if (event.type === "draw") return `${name} ツモ ${tile}`;
  if (event.type === "discard") return `${name} 打 ${tile}`;
  if (event.type === "call") return `${name} 副露 ${tile}`;
  if (event.type === "riichi") return `${name} リーチ`;
  if (event.type === "decision") return `${name} 判断 ${event.action}${tile ? ` ${tile}` : ""}`;
  return `${event.type} ${name} ${tile}`;
}

function compactTile(tile) {
  if (!tile) return null;
  return {
    index: tile.tileIndex ?? tile.index,
    mark: tile.mark,
    red: tile.tone === "flower",
  };
}

function saveCurrentPaifu() {
  if (!state.currentPaifu) return;
  const no = state.currentPaifu.no;
  try {
    localStorage.setItem(paifuStorageKey(no), JSON.stringify(state.currentPaifu));
    const index = getPaifuIndex().filter((item) => item.no !== no);
    index.unshift({
      no,
      startedAt: state.currentPaifu.startedAt,
      finishedAt: state.currentPaifu.finishedAt ?? null,
      gameType: state.currentPaifu.rules.gameType,
      mode: state.currentPaifu.rules.learningMode,
      rounds: state.currentPaifu.rounds.length,
    });
    const trimmed = index.slice(0, maxStoredPaifu);
    localStorage.setItem(paifuIndexKey, JSON.stringify(trimmed));
    index.slice(maxStoredPaifu).forEach((item) => localStorage.removeItem(paifuStorageKey(item.no)));
  } catch (error) {
    console.error(error);
    log(`牌譜保存に失敗しました: ${error.message}`);
  }
}

function getPaifuIndex() {
  try {
    return JSON.parse(localStorage.getItem(paifuIndexKey) || "[]");
  } catch {
    return [];
  }
}

function paifuStorageKey(no) {
  return `mahjongPaifu:${no}`;
}

function openPaifuViewer() {
  renderPaifuIndex();
  $("paifuOverlay").hidden = false;
}

function closePaifuViewer() {
  $("paifuOverlay").hidden = true;
}

function loadPaifuByNumber() {
  const no = Number($("paifuNumberInput").value);
  if (!no) {
    $("paifuDetail").textContent = "牌譜番号を入力してください。";
    return;
  }
  try {
    const paifu = JSON.parse(localStorage.getItem(paifuStorageKey(no)) || "null");
    if (!paifu) {
      $("paifuDetail").textContent = `No.${no} の牌譜は見つかりません。`;
      return;
    }
    state.paifuViewer = paifu;
    state.paifuViewerRound = 0;
    state.paifuViewerStep = 0;
    renderPaifuDetail(paifu);
  } catch (error) {
    $("paifuDetail").textContent = `牌譜を読めませんでした: ${error.message}`;
  }
}

function renderPaifuIndex() {
  const index = getPaifuIndex();
  $("paifuNumberInput").value = index[0]?.no ?? "";
  $("paifuList").innerHTML = index.slice(0, 12)
    .map((item) => `<button data-paifu-no="${item.no}">No.${item.no} ${paifuGameTypeLabel(item.gameType)} ${item.rounds}局</button>`)
    .join("") || "<div>保存された牌譜はまだありません。</div>";
  document.querySelectorAll("[data-paifu-no]").forEach((button) => {
    button.addEventListener("click", () => {
      $("paifuNumberInput").value = button.dataset.paifuNo;
      loadPaifuByNumber();
    });
  });
  $("paifuDetail").textContent = index.length ? "番号を選ぶか入力して表示します。" : "";
  $("paifuRoundSelect").innerHTML = "";
  $("paifuStepLabel").textContent = "-";
}

function renderPaifuDetail(paifu) {
  state.paifuViewer = paifu;
  state.paifuViewerRound = Math.min(state.paifuViewerRound ?? 0, Math.max(0, paifu.rounds.length - 1));
  state.paifuViewerStep = Math.min(state.paifuViewerStep ?? 0, Math.max(0, currentPaifuViewerSnapshots().length - 1));
  renderPaifuRoundSelect(paifu);
  renderPaifuReplayStep();
}

function renderPaifuSummary(paifu) {
  const lines = [
    `No.${paifu.no} / ${paifuGameTypeLabel(paifu.rules.gameType)} / ${paifu.rules.learningMode}`,
    `開始 ${formatPaifuDate(paifu.startedAt)}${paifu.finishedAt ? ` / 終了 ${formatPaifuDate(paifu.finishedAt)}` : ""}`,
    paifu.result ? `結果: ${paifu.result.rankings.map((item) => `${item.rank}位 ${item.name} ${item.score}`).join(" / ")}` : "結果: 対局中または未完了",
    "",
    ...paifu.rounds.map((round, index) => paifuRoundText(round, index + 1)),
  ];
  return lines.join("\n");
}

function renderPaifuRoundSelect(paifu) {
  $("paifuRoundSelect").innerHTML = paifu.rounds
    .map((round, index) => `<option value="${index}">${index + 1}. ${round.label} ${round.honba}本場</option>`)
    .join("");
  $("paifuRoundSelect").value = String(state.paifuViewerRound ?? 0);
}

function currentPaifuViewerRound() {
  return state.paifuViewer?.rounds?.[state.paifuViewerRound ?? 0] ?? null;
}

function currentPaifuViewerSnapshots() {
  const round = currentPaifuViewerRound();
  if (!round) return [];
  if (round.snapshots?.length) return round.snapshots;
  return [legacyPaifuSnapshot(round)];
}

function legacyPaifuSnapshot(round) {
  return {
    label: "保存形式が古いため要約のみ表示",
    current: round.dealer,
    wallCount: null,
    scores: round.scoresEnd ?? round.scoresStart ?? {},
    hands: round.startingHands ?? {},
    rivers: {},
    melds: {},
  };
}

function renderPaifuReplayStep() {
  const paifu = state.paifuViewer;
  const round = currentPaifuViewerRound();
  const snapshots = currentPaifuViewerSnapshots();
  const step = Math.max(0, Math.min(state.paifuViewerStep ?? 0, snapshots.length - 1));
  state.paifuViewerStep = step;
  const snapshot = snapshots[step];
  $("paifuStepLabel").textContent = `${step + 1} / ${snapshots.length}`;
  $("paifuPrevButton").disabled = step <= 0;
  $("paifuNextButton").disabled = step >= snapshots.length - 1;
  if (!paifu || !round || !snapshot) {
    $("paifuDetail").textContent = "牌譜を選択してください。";
    return;
  }
  $("paifuDetail").textContent = [
    renderPaifuSummary(paifu),
    "",
    `再生: ${round.label} ${round.honba}本場 / ${snapshot.label}`,
    `手番: ${snapshot.current ? playerSeatLabel(snapshot.current) : "-"} / 残り ${snapshot.wallCount ?? "-"}枚`,
    `点数: ${players.map((player) => `${playerSeatLabel(player)} ${snapshot.scores?.[player] ?? "-"}`).join(" / ")}`,
    "",
    ...paifuDecisionLines(round, step),
    "",
    ...players.map((player) => paifuSnapshotPlayerLine(player, snapshot)),
  ].join("\n");
}

function paifuRoundText(round, index) {
  const outcome = round.outcome
    ? round.outcome.type === "agari"
      ? `${round.outcome.method} ${round.outcome.winnerName} ${round.outcome.tile?.mark ?? ""} ${round.outcome.pointText ?? ""}`
      : `流局 聴牌: ${round.outcome.tenpaiNames?.join("、") || "なし"}`
    : "未完了";
  const events = round.events.slice(-10).map((event) => {
    const name = event.player ? playerSeatLabel(event.player) : "";
    return event.type === "decision"
      ? `判断:${name}${event.action}${event.tile?.mark ?? ""}`
      : `${event.type}:${name}${event.tile?.mark ?? ""}`;
  }).join(" / ");
  return `${index}. ${round.label} ${round.honba}本場 親:${playerSeatLabel(round.dealer)} ドラ:${round.doraIndicator?.mark ?? "-"}\n  ${outcome}\n  終盤ログ: ${events}`;
}

function paifuDecisionLines(round, step) {
  const decision = (round.events ?? [])[step - 1];
  if (decision?.type !== "decision") return [];
  const alternatives = decision.alternatives?.length
    ? ` / 候補: ${decision.alternatives.map((item) => `${item.tile?.mark ?? "-"}(${item.score ?? "-"})`).join("、")}`
    : "";
  return [
    `CPU判断: ${playerSeatLabel(decision.player)} ${decision.action}${decision.tile?.mark ? ` ${decision.tile.mark}` : ""}`,
    `理由: ${decision.reason || "-"} / 評価 ${decision.score ?? "-"} / 向聴 ${decision.shanten ?? "-"} / 待ち ${decision.waits ?? "-"}${alternatives}`,
  ];
}

function paifuSnapshotPlayerLine(player, snapshot) {
  const hand = snapshot.hands?.[player]?.map((tile) => tile?.mark).join(" ") || "-";
  const river = snapshot.rivers?.[player]?.map((entry) => `${entry.sideways ? "横" : ""}${entry.tile?.mark ?? ""}`).join(" ") || "-";
  const melds = snapshot.melds?.[player]?.map((meld) => `${meld.type}[${meld.tiles.map((tile) => tile.mark).join(" ")}]`).join(" / ") || "-";
  return `${playerSeatLabel(player)}\n  手牌: ${hand}\n  河: ${river}\n  副露: ${melds}`;
}

function setPaifuViewerRound(index) {
  if (!state.paifuViewer) return;
  state.paifuViewerRound = Math.max(0, Math.min(Number(index), state.paifuViewer.rounds.length - 1));
  state.paifuViewerStep = 0;
  renderPaifuReplayStep();
}

function stepPaifuViewer(delta) {
  if (!state.paifuViewer) return;
  const snapshots = currentPaifuViewerSnapshots();
  state.paifuViewerStep = Math.max(0, Math.min((state.paifuViewerStep ?? 0) + delta, snapshots.length - 1));
  renderPaifuReplayStep();
}

function paifuGameTypeLabel(gameType) {
  return gameType === "hanchan" ? "東南戦" : "東風戦";
}

function formatPaifuDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("ja-JP");
}
