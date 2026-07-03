function render() {
  if (isFastLearningMode() && !state.roundEnded && !state.gameEnded) {
    renderFastLearningHud();
    return;
  }
  renderHands();
  renderRivers();
  renderHud();
}

function renderFastLearningHud() {
  $("wallCount").textContent = Math.max(0, state.wall.length - 14);
  $("roundLabel").textContent = `${roundWind()} ${state.round} 局`;
  $("honbaLabel").textContent = `${state.honba} 本場 / 供託 ${state.riichiSticks}`;
  $("roomLabel").textContent = `${gameTypeLabel()} / ${seatModeLabel()} / No.${state.paifuTrialNo || "-"} / ${ruleSummaryLabel()}`;
  $("turnLabel").textContent = state.paused ? "停止中" : "高速学習中";
  players.forEach((visualSeat) => {
    const player = playerAtVisualSeat(visualSeat);
    $(`score-${visualSeat}`).textContent = state.scores[player];
  });
  renderDora();
  renderPauseControls();
}

function renderHands() {
  renderPlayerHand(playerAtVisualSeat("bottom"));
  ["top", "left", "right"].forEach((visualSeat) => {
    const player = playerAtVisualSeat(visualSeat);
    const container = $(`hand-${visualSeat}`);
    container.innerHTML = "";
    state.hands[player].forEach((tile, index) => {
      const element =
        isHandVisible(player)
          ? createTile(tile, { small: true, revealed: true })
          : createTile(null, { back: true, small: true });
      if (player === "bottom") {
        element.addEventListener("click", () => {
          if (!canDiscardFromHand()) return;
          discard("bottom", index);
        });
      }
      container.appendChild(element);
    });
  });
}

function renderPlayerHand(player) {
  const container = $("hand-bottom");
  container.innerHTML = "";

  state.hands[player].forEach((tile, index) => {
    const element = isHandVisible(player) ? createTile(tile) : createTile(null, { back: true });
    if (index === state.hands[player].length - 1 && state.current === player && !state.awaitingDraw) {
      element.classList.add("drawn");
    }
    element.addEventListener("click", () => {
      if (player !== "bottom" || !canDiscardFromHand()) return;
      discard("bottom", index);
    });
    container.appendChild(element);
  });
}

function isHandVisible(player) {
  if (state.revealedHands[player]) return true;
  return state.viewSeat === player;
}

function canDiscardFromHand() {
  return !state.paused && state.current === "bottom" && !state.awaitingDraw && !state.autoTsumogiri && state.hands.bottom.length % 3 === 2;
}

function baseHandSize(player) {
  return 13 - state.melds[player].length * 3;
}

function renderRivers() {
  players.forEach((visualSeat) => {
    const player = playerAtVisualSeat(visualSeat);
    const container = $(`river-${visualSeat}`);
    container.innerHTML = "";
    state.rivers[player].forEach((entry) => container.appendChild(createTile(entry.tile, { small: true, sideways: entry.sideways })));
  });
}

function renderHud() {
  $("wallCount").textContent = Math.max(0, state.wall.length - 14);
  $("roundLabel").textContent = `${roundWind()} ${state.round} 局`;
  $("honbaLabel").textContent = `${state.honba} 本場 / 供託 ${state.riichiSticks}`;
  $("roomLabel").textContent = `${gameTypeLabel()} / ${seatModeLabel()} / No.${state.paifuTrialNo || "-"} / ${ruleSummaryLabel()}`;
  $("gameTypeButton").textContent = "ルール";
  $("turnLabel").textContent = state.paused ? "停止中" : state.autoTsumogiri ? "自動ツモ切り" : state.current === "bottom" ? "打牌待ち" : state.current === "call" ? "副露選択" : state.current === "ron" ? "和了選択" : "相手思考中";
  $("drawButton").disabled = true;
  $("tsumoButton").hidden = !canTsumo();
  $("ronButton").disabled = isCpuOnlyMode() || !canRon();
  $("kanButton").disabled = isCpuOnlyMode() || !canKan();
  $("noCallButton").disabled = isCpuOnlyMode();
  $("noCallButton").setAttribute("aria-pressed", String(state.noCallMode));
  $("noCallButton").classList.toggle("active", state.noCallMode);
  $("riichiButton").hidden = !canRiichi();
  $("waitToggleButton").setAttribute("aria-pressed", String(state.waitDisplay));
  $("waitToggleButton").classList.toggle("active", state.waitDisplay);
  $("waitToggleButton").hidden = getVisibleWaits().length === 0;
  $("autoWinButton").hidden = !canShowAutoWinButton();
  $("autoWinButton").setAttribute("aria-pressed", String(state.autoWin));
  $("autoWinButton").classList.toggle("active", state.autoWin);
  renderPauseControls();
  renderViewSwitch();

  players.forEach((visualSeat) => {
    const player = playerAtVisualSeat(visualSeat);
    $(`score-${visualSeat}`).textContent = state.scores[player];
  });
  renderSeatLabels();
  renderMelds();
  renderDora();

  renderCallPanel();
  renderWaitPanel();
}

function renderPauseControls() {
  $("pauseButton").disabled = state.paused || !state.gameStarted || state.gameEnded;
  $("resumeButton").disabled = !state.paused || !state.gameStarted;
}

function renderDora() {
  const container = $("doraIndicator");
  const actual = $("doraActual");
  container.innerHTML = "";
  if (state.doraIndicator) {
    container.appendChild(createTile(state.doraIndicator, { small: true }));
    actual.textContent = `ドラ: ${getDoraTileType(state.doraIndicator).mark}`;
  } else {
    actual.textContent = "";
  }
}

function renderMelds() {
  const container = $("melds-bottom");
  const owner = playerAtVisualSeat("bottom");
  container.innerHTML = "";
  [...state.melds[owner]].reverse().forEach((meld) => {
    const meldElement = document.createElement("div");
    meldElement.className = `meld from-${relativeVisualSeat(meld.fromPlayer, owner)}`;
    meld.tiles.forEach((tile, index) => {
      const element = createTile(tile);
      if (index === meld.claimedIndex) element.classList.add("claimed");
      meldElement.appendChild(element);
    });
    container.appendChild(meldElement);
  });
}

function createTile(tile, options = {}) {
  const element = document.createElement("div");
  element.className = "tile";

  if (options.small) element.classList.add("small");
  if (options.sideways) element.classList.add("sideways");
  if (options.revealed) element.classList.add("revealed");
  if (options.back) {
    element.classList.add("back");
    return element;
  }

  element.textContent = tile.mark;
  if (tile.tone) element.classList.add(tile.tone);
  return element;
}

function playerName(player) {
  return `${seatWind(player)}家 ${playerSeatLabel(player)}`;
}

function roundWind() {
  return windOrder[state.roundWindIndex];
}

function gameTypeLabel() {
  return state.gameType === "hanchan" ? "東南戦" : "東風戦";
}

function seatModeLabel() {
  return state.rules.seatMode === "cpu4" ? "CPU4体観戦" : "Player+CPU3体";
}

function ruleSummaryLabel() {
  const items = [
    state.rules.tobi ? "飛びあり" : "飛びなし",
    state.rules.redDora ? "赤あり" : "赤なし",
    state.rules.abortiveDraws ? "途中流局あり" : "途中流局なし",
  ];
  return items.join(" / ");
}

function playerSeatLabel(player) {
  if (player === "bottom" && isCpuOnlyMode()) return "CPU-A";
  if (isCpuOnlyMode() && player === "right") return "CPU-B";
  if (isCpuOnlyMode() && player === "top") return "CPU-C";
  if (isCpuOnlyMode() && player === "left") return "CPU-D";
  return playerLabels[player];
}

function seatWind(player) {
  const offset = (players.indexOf(player) - state.dealerIndex + players.length) % players.length;
  return windOrder[offset];
}

function renderSeatLabels() {
  players.forEach((visualSeat) => {
    const player = playerAtVisualSeat(visualSeat);
    $(`wind-${visualSeat}`).textContent = seatWind(player);
  });
  $("tag-bottom").textContent = `${seatWind(playerAtVisualSeat("bottom"))} / ${playerSeatLabel(playerAtVisualSeat("bottom"))}`;
  $("tag-right").textContent = `${seatWind(playerAtVisualSeat("right"))} / ${playerSeatLabel(playerAtVisualSeat("right"))}`;
  $("tag-top").textContent = `${seatWind(playerAtVisualSeat("top"))} / ${playerSeatLabel(playerAtVisualSeat("top"))}`;
  $("tag-left").textContent = `${seatWind(playerAtVisualSeat("left"))} / ${playerSeatLabel(playerAtVisualSeat("left"))}`;
}

function playerAtVisualSeat(visualSeat) {
  const viewIndex = players.indexOf(state.viewSeat);
  const visualOffset = players.indexOf(visualSeat);
  return players[(viewIndex + visualOffset) % players.length];
}

function relativeVisualSeat(player, originPlayer) {
  const offset = (players.indexOf(player) - players.indexOf(originPlayer) + players.length) % players.length;
  return players[offset];
}

function renderViewSwitch() {
  $("playerButton").textContent = `視点: ${playerSeatLabel(state.viewSeat)}`;
  document.querySelectorAll("[data-view-seat]").forEach((button) => {
    const seat = button.dataset.viewSeat;
    button.textContent = playerSeatLabel(seat);
    button.classList.toggle("active", state.viewSeat === seat);
  });
}

function renderLearningSummary() {
  const summary = $("learningSummary");
  if (!summary) return;
  const paifuCounts = getLearningCountsFromPaifu();
  const usePaifuCounts = paifuCounts.total > 0;
  const tonpuu = usePaifuCounts ? paifuCounts.tonpuu : state.ai.gamesByType?.tonpuu ?? 0;
  const hanchan = usePaifuCounts ? paifuCounts.hanchan : state.ai.gamesByType?.hanchan ?? 0;
  const known = usePaifuCounts ? paifuCounts.total : tonpuu + hanchan;
  const legacy = Math.max(0, (state.ai.games ?? 0) - known);
  const modeLabel = { standard: "通常", accelerated: "強化", fast: "高速" }[state.rules.learningMode] ?? "通常";
  const latestPaifu = getPaifuIndex()[0]?.no ?? "-";
  summary.innerHTML = [
    `<strong>CPU学習</strong> ${modeLabel} / 東風戦 ${tonpuu}試合 / 東南戦 ${hanchan}試合 / 合計 ${state.ai.games ?? 0}試合`,
    `<span>最新牌譜 No.${latestPaifu}</span>`,
    legacy > 0 ? `<span>${usePaifuCounts ? "牌譜未保存" : "旧データ"} ${legacy}試合は形式内訳なし</span>` : "",
  ].filter(Boolean).join("<br>");
}

function getLearningCountsFromPaifu() {
  const index = typeof getPaifuIndex === "function" ? getPaifuIndex() : [];
  return index.reduce((counts, item) => {
    if (item.gameType === "hanchan") counts.hanchan += 1;
    else if (item.gameType === "tonpuu") counts.tonpuu += 1;
    counts.total += 1;
    return counts;
  }, { tonpuu: 0, hanchan: 0, total: 0 });
}

function toggleViewSwitch() {
  $("viewSwitch").hidden = !$("viewSwitch").hidden;
}

function setViewSeat(seat) {
  state.viewSeat = seat;
  $("viewSwitch").hidden = true;
  log(`${playerSeatLabel(seat)}視点に切り替えました。`);
  render();
}

function log(message) {
  $("messageLog").textContent = message;
}
