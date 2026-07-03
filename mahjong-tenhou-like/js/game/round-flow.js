function startRound() {
  clearCpuTimer();
  clearDrawTimer();
  clearCpuHeartbeat();
  $("drawOverlay").hidden = true;
  state.wall = buildWall();
  state.doraIndicator = state.wall[0] || null;
  state.uraDoraIndicator = state.wall[1] || null;
  state.riichi = false;
  state.riichiPlayers = {};
  state.ippatsuEligible = {};
  state.riichiPending = false;
  state.roundEnded = false;
  state.gameEnded = false;
  state.lastWinner = null;
  state.current = players[state.dealerIndex];
  state.awaitingDraw = true;
  state.autoTsumogiri = false;
  state.lastDiscard = null;
  state.callChoices = [];
  state.noCallMode = false;
  state.autoWin = false;
  state.ronPending = false;
  state.pendingRon = null;
  state.drawOk = {};
  state.pendingDrawGameEnd = false;

  players.forEach((player) => {
    state.hands[player] = [];
    state.rivers[player] = [];
    state.melds[player] = [];
    state.openYakuPlans[player] = null;
    state.revealedHands[player] = false;
  });

  for (let count = 0; count < 13; count += 1) {
    players.forEach((player) => draw(player));
  }
  players.forEach((player) => sortHand(player));
  startPaifuRound();
  log(`${playerName(players[state.dealerIndex])}の第一ツモです。`);
  render();
  markCpuProgress();
  if (isCpuOnlyMode()) {
    startCpuPump();
    return;
  }
  scheduleCpu(startDealerTurn, 250);
}

function draw(player) {
  const tile = state.wall.pop();
  if (tile) {
    state.hands[player].push(tile);
    recordPaifuEvent("draw", { player, tile });
    markCpuProgress();
  }
  return tile;
}

function discard(player, tileIndex) {
  if (state.riichiPending === player && !keepsTenpaiAfterDiscard(player, tileIndex)) {
    log("リーチ宣言牌は聴牌を維持する牌だけ切れます。");
    render();
    return false;
  }
  const [tile] = state.hands[player].splice(tileIndex, 1);
  if (!tile) return false;

  const sideways = state.riichiPending === player;
  state.rivers[player].push({ tile, sideways });
  state.lastDiscard = { player, tile };
  recordPaifuEvent("discard", { player, tile, sideways });
  state.riichiPending = false;
  if (state.riichiPlayers[player] && !sideways) {
    state.ippatsuEligible[player] = false;
  }
  sortHand(player);
  log(`${playerName(player)} 打 ${tile.mark}`);
  markCpuProgress();

  if (player !== "bottom" && !isCpuOnlyMode() && canRon()) {
    if (state.autoWin) {
      showAgari("bottom", "ロン", tile, player);
      return true;
    }
    state.current = "ron";
    state.ronPending = true;
    state.pendingRon = { winner: "bottom", tile, discarder: player };
    log(`${tile.mark}でロンできます。ロン、またはスキップを選んでください。`);
    render();
    return true;
  }

  const ronWinner = findRonWinner(player, tile);
  if (ronWinner) {
    showAgari(ronWinner, "ロン", tile, player);
    return true;
  }

  const cpuCall = (isCpuOnlyMode() || player === "bottom") ? findCpuCall(player, tile) : null;
  if (cpuCall) {
    claimCpuCall(cpuCall);
    return true;
  }

  if (state.wall.length <= 14) {
    endExhaustiveDraw();
    return true;
  }

  if (isCpuOnlyMode()) {
    render();
    return true;
  }

  if (player === "bottom") {
    state.current = "right";
    state.awaitingDraw = false;
    state.callChoices = [];
    render();
    scheduleCpu(() => continueCpuCycle(0), 420);
  } else {
    state.callChoices = getCallChoices(tile, player);
    if (state.callChoices.length > 0) {
      state.current = "call";
      render();
      return true;
    }
  }

  render();
  return true;
}

function startDealerTurn() {
  if (state.paused) {
    state.resumeAction = startDealerTurn;
    return;
  }
  if (isCpuOnlyMode()) {
    continueCpuOnlyCycle(state.dealerIndex);
    return;
  }
  const dealer = players[state.dealerIndex];
  if (dealer === "bottom") {
    startPlayerTurn("bottom");
    return;
  }

  const cpuPlayers = ["right", "top", "left"];
  const startIndex = cpuPlayers.indexOf(dealer);
  continueCpuCycle(startIndex >= 0 ? startIndex : 0);
}

function isCpuOnlyMode() {
  return state.rules.seatMode === "cpu4";
}

function isFastLearningMode() {
  return isCpuOnlyMode() && state.rules.autoSelfPlay && state.rules.learningMode === "fast";
}

function cpuDelay(milliseconds) {
  if (isFastLearningMode()) return Math.max(8, Math.min(24, milliseconds));
  if (state.rules.learningMode === "accelerated") return Math.max(20, Math.floor(milliseconds * 0.35));
  return milliseconds;
}

function clearCpuTimer() {
  if (!state.cpuTimer) return;
  clearTimeout(state.cpuTimer);
  state.cpuTimer = null;
  state.cpuTimerStartedAt = 0;
}

function clearCpuWatchdog() {
  if (!state.cpuWatchdogTimer) return;
  clearTimeout(state.cpuWatchdogTimer);
  state.cpuWatchdogTimer = null;
}

function clearCpuPump() {
  if (!state.cpuPumpTimer) return;
  clearInterval(state.cpuPumpTimer);
  state.cpuPumpTimer = null;
}

function scheduleCpu(action, milliseconds) {
  if (isCpuOnlyMode() && state.cpuPumpTimer) {
    return;
  }
  clearCpuTimer();
  clearCpuWatchdog();
  state.cpuTimer = setTimeout(() => {
    state.cpuTimer = null;
    state.cpuTimerStartedAt = 0;
    try {
      action();
    } catch (error) {
      console.error(error);
      log(`CPU処理エラーを検出しました: ${error.message}`);
      try {
        recoverCpuOnlyStall(true);
      } catch (recoverError) {
        console.error(recoverError);
        log(`CPU復旧処理を退避します: ${recoverError.message}`);
        forceCpuProgressAfterError(recoverError);
      }
    }
  }, cpuDelay(milliseconds));
  state.cpuTimerStartedAt = Date.now();
  if (isCpuOnlyMode()) {
    state.cpuWatchdogTimer = setTimeout(recoverCpuOnlyStall, Math.max(1200, cpuDelay(milliseconds) + 1000));
  }
}

function startCpuHeartbeat() {
  clearCpuHeartbeat();
  markCpuProgress();
  state.cpuHeartbeatTimer = setInterval(() => {
    try {
      if (!state.gameStarted || !isCpuOnlyMode() || state.paused) return;
      const staleTimer = state.cpuTimer && Date.now() - state.cpuTimerStartedAt > 900;
      if (staleTimer) {
        log("古いCPU予約を破棄して進行を復旧します。");
        recoverCpuOnlyStall(true);
        return;
      }
      const key = cpuProgressKey();
      if (key !== state.lastProgressKey) {
        markCpuProgress();
        return;
      }
      if (Date.now() - state.lastProgressAt < 900) return;
      recoverCpuOnlyStall(true);
    } catch (error) {
      console.error(error);
      log(`CPU監視エラーを検出しました: ${error.message}`);
      forceCpuProgressAfterError(error);
    }
  }, 300);
}

function startCpuPump() {
  if (!isCpuOnlyMode() || state.cpuPumpTimer) return;
  clearCpuTimer();
  clearCpuWatchdog();
  state.cpuPumpTimer = setInterval(cpuOnlyPumpStep, cpuDelay(120));
}

function cpuOnlyPumpStep() {
  try {
    if (!state.gameStarted || !isCpuOnlyMode() || state.paused) return;
    if (state.gameEnded) {
      if (state.rules.autoSelfPlay && (!state.autoNextGameAt || Date.now() >= state.autoNextGameAt)) {
        state.autoNextGameAt = 0;
        startGame();
      }
      return;
    }
    if (state.roundEnded || state.current === "ended") {
      if (state.lastWinner) {
        advanceAfterAgari();
      } else {
        proceedAfterDraw();
      }
      return;
    }
    if (state.wall.length <= 14) {
      endExhaustiveDraw();
      return;
    }

    const player = players.includes(state.current) ? state.current : players[state.dealerIndex];
    state.current = player;
    const base = baseHandSize(player);
    const handLength = state.hands[player]?.length ?? 0;

    if (handLength <= base) {
      const drawnTile = draw(player);
      if (drawnTile && isValidAgariForPlayer(player, "ツモ")) {
        showAgari(player, "ツモ", drawnTile);
        return;
      }
      log(`${playerName(player)} ツモ`);
      render();
      return;
    }

    if (handLength >= base + 1) {
      const riichiDiscard = !state.riichiPlayers[player] ? findRiichiDiscardIndex(player) : -1;
      if (riichiDiscard !== -1 && shouldCpuRiichi(player, waitsAfterDiscard(player, riichiDiscard))) {
        declareRiichiFor(player);
        log(`${playerName(player)} リーチ`);
      }
      const index = state.riichiPending === player ? riichiDiscard : state.riichiPlayers[player] ? state.hands[player].length - 1 : chooseCpuDiscard(state.hands[player], player);
      discardCpuTile(player, index);
      if (!state.roundEnded && state.current === player) {
        state.current = nextPlayer(player);
      }
      render();
    }
  } catch (error) {
    console.error(error);
    log(`CPUポンプエラーを検出しました: ${error.message}`);
    forceCpuProgressAfterError(error);
  }
}

function clearCpuHeartbeat() {
  if (!state.cpuHeartbeatTimer) return;
  clearInterval(state.cpuHeartbeatTimer);
  state.cpuHeartbeatTimer = null;
}

function markCpuProgress() {
  state.lastProgressKey = cpuProgressKey();
  state.lastProgressAt = Date.now();
}

function cpuProgressKey() {
  const playerStates = players
    .map((player) => [
      player,
      state.hands[player]?.length ?? 0,
      state.rivers[player]?.length ?? 0,
      state.melds[player]?.length ?? 0,
      state.scores[player] ?? 0,
    ].join(":"))
    .join("|");
  return [
    state.gameStarted,
    state.roundEnded,
    state.gameEnded,
    state.pendingDrawGameEnd,
    state.current,
    state.roundWindIndex,
    state.round,
    state.honba,
    state.dealerIndex,
    state.wall.length,
    state.riichiSticks,
    playerStates,
  ].join("/");
}

function discardCpuTile(player, tileIndex) {
  const ok = discard(player, tileIndex);
  if (ok) return true;
  if (!state.hands[player]?.length) return false;
  state.riichiPending = false;
  const fallbackIndex = state.riichiPlayers[player]
    ? state.hands[player].length - 1
    : chooseCpuDiscard(state.hands[player], player);
  log(`${playerName(player)}の打牌を復旧しました。`);
  return discard(player, fallbackIndex);
}

function recoverCpuOnlyStall(force = false) {
  state.cpuWatchdogTimer = null;
  if (!isCpuOnlyMode() || state.paused || !state.gameStarted) return;
  if (!force && state.cpuTimer) return;
  clearCpuTimer();
  clearCpuWatchdog();

  if (state.gameEnded) {
    if (state.rules.autoSelfPlay) {
      log("終局後の自動連戦を復旧しました。");
      scheduleCpu(startGame, 120);
    }
    return;
  }

  if (state.roundEnded || state.current === "ended") {
    log("局終了後の自動進行を復旧しました。");
    if (state.lastWinner) {
      scheduleCpu(advanceAfterAgari, 120);
      return;
    }
    scheduleCpu(proceedAfterDraw, 120);
    return;
  }

  if (!players.includes(state.current)) {
    state.current = players[state.dealerIndex];
    scheduleCpu(startDealerTurn, 120);
    return;
  }

  if (state.wall.length <= 14) {
    endExhaustiveDraw();
    return;
  }

  const player = state.current;
  const playerIndex = players.indexOf(player);
  const handLength = state.hands[player]?.length ?? 0;
  const waitingToDiscard = handLength === baseHandSize(player) + 1;
  log("CPU進行を復旧しています。");

  if (waitingToDiscard) {
    const riichiDiscard = !state.riichiPlayers[player] ? findRiichiDiscardIndex(player) : -1;
    if (riichiDiscard !== -1 && shouldCpuRiichi(player, waitsAfterDiscard(player, riichiDiscard))) {
      declareRiichiFor(player);
      log(`${playerName(player)} リーチ`);
    }
    const index = state.riichiPending === player ? riichiDiscard : state.riichiPlayers[player] ? handLength - 1 : chooseCpuDiscard(state.hands[player], player);
    discardCpuTile(player, index);
    if (state.current === "call" || state.current === "ron" || state.current === "ended" || state.current !== player) return;
    scheduleCpu(() => continueCpuOnlyCycle((playerIndex + 1) % players.length), 240);
    return;
  }

  continueCpuOnlyCycle(playerIndex);
}

function forceCpuProgressAfterError(error) {
  if (!isCpuOnlyMode() || state.paused || !state.gameStarted) return;
  clearCpuTimer();
  clearCpuWatchdog();
  try {
    skipBrokenRoundAfterError(error);
  } catch (fallbackError) {
    console.error(fallbackError);
    log(`復旧フォールバックも失敗しました: ${fallbackError.message}`);
    emergencyRestartCpuGame(fallbackError);
  }
}

function skipBrokenRoundAfterError(error) {
  log(`エラー局をスキップして次局へ進めます: ${error.message}`);
  try {
    finishPaifuRound({
      type: "error-skip",
      message: error.message,
      scores: { ...state.scores },
    });
  } catch (paifuError) {
    console.error(paifuError);
  }

  $("scoreOverlay").hidden = true;
  $("drawOverlay").hidden = true;
  state.roundEnded = false;
  state.gameEnded = false;
  state.lastWinner = null;
  state.current = "ended";
  state.callChoices = [];
  state.ronPending = false;
  state.riichiPending = false;
  state.autoTsumogiri = false;
  state.honba += 1;
  advanceHand();

  if (isGameComplete()) {
    try {
      showGameResult();
    } catch (resultError) {
      console.error(resultError);
      log(`終局処理をスキップして新しい試合へ進めます: ${resultError.message}`);
      startGame();
    }
    return;
  }

  startRound();
}

function emergencyRestartCpuGame(error) {
  try {
    log(`緊急復旧として新しい試合へ進めます: ${error.message}`);
    clearCpuTimer();
    clearCpuWatchdog();
    $("scoreOverlay").hidden = true;
    $("drawOverlay").hidden = true;
    state.roundEnded = true;
    state.gameEnded = true;
    state.current = "ended";
    startGame();
  } catch (restartError) {
    console.error(restartError);
    log(`緊急復旧に失敗しました: ${restartError.message}`);
  }
}

function pauseGame() {
  if (!state.gameStarted || state.gameEnded || state.paused) return;
  clearCpuTimer();
  clearCpuWatchdog();
  state.paused = true;
  log("対局を停止しました。");
  render();
}

function resumeGame() {
  if (!state.paused) return;
  state.paused = false;
  const action = state.resumeAction;
  state.resumeAction = null;
  log("対局を再開しました。");
  render();
  if (action) {
    scheduleCpu(action, 40);
    return;
  }
  resumeCurrentFlow();
}

function resumeCurrentFlow() {
  if (state.roundEnded || state.gameEnded) return;
  if (isCpuOnlyMode() && players.includes(state.current)) {
    recoverCpuOnlyStall();
    return;
  }
  const cpuPlayers = ["right", "top", "left"];
  if (cpuPlayers.includes(state.current)) {
    continueCpuCycle(cpuPlayers.indexOf(state.current));
  }
}

function openExitConfirm() {
  state.pausedBeforeExitConfirm = state.paused;
  state.paused = true;
  $("exitConfirmOverlay").hidden = false;
  log("対局終了の確認中です。");
  render();
}

function cancelExitConfirm() {
  $("exitConfirmOverlay").hidden = true;
  const shouldResume = !state.pausedBeforeExitConfirm;
  state.pausedBeforeExitConfirm = false;
  if (shouldResume) {
    resumeGame();
    return;
  }
  render();
}

function confirmExitToLobby() {
  clearCpuTimer();
  clearCpuWatchdog();
  clearCpuHeartbeat();
  clearCpuPump();
  clearDrawTimer();
  $("exitConfirmOverlay").hidden = true;
  $("scoreOverlay").hidden = true;
  $("drawOverlay").hidden = true;
  state.paused = false;
  state.resumeAction = null;
  state.pausedBeforeExitConfirm = false;
  state.roundEnded = true;
  state.gameEnded = true;
  state.gameStarted = false;
  state.current = "ended";
  log("対局を終了しました。");
  openLobby();
}

function continueCpuOnlyCycle(playerIndex = 0) {
  if (state.paused) {
    state.resumeAction = () => continueCpuOnlyCycle(playerIndex);
    return;
  }
  if (state.roundEnded || state.current === "ended") return;
  if (state.wall.length <= 14) {
    endExhaustiveDraw();
    return;
  }
  const player = players[playerIndex % players.length];
  state.pendingCpuIndex = 0;
  state.current = player;
  const drawnTile = draw(player);
  if (drawnTile && isValidAgariForPlayer(player, "ツモ")) {
    showAgari(player, "ツモ", drawnTile);
    return;
  }
  log(`${playerName(player)} ツモ`);
  render();
  scheduleCpu(() => {
    if (state.paused) {
      state.resumeAction = () => continueCpuOnlyCycle(playerIndex);
      return;
    }
    if (state.roundEnded || state.current !== player) return;
    const riichiDiscard = !state.riichiPlayers[player] ? findRiichiDiscardIndex(player) : -1;
    if (riichiDiscard !== -1 && shouldCpuRiichi(player, waitsAfterDiscard(player, riichiDiscard))) {
      declareRiichiFor(player);
      log(`${playerName(player)} リーチ`);
    }
    const index = state.riichiPending === player ? riichiDiscard : state.riichiPlayers[player] ? state.hands[player].length - 1 : chooseCpuDiscard(state.hands[player], player);
    const discarded = discardCpuTile(player, index);
    if (!discarded) {
      scheduleCpu(() => continueCpuOnlyCycle((playerIndex + 1) % players.length), 480);
      return;
    }
    if (state.current === "ended" || state.current !== player) return;
    scheduleCpu(() => continueCpuOnlyCycle((playerIndex + 1) % players.length), 480);
  }, 360);
}

function continueCpuCycle(startIndex = 0) {
  if (state.paused) {
    state.resumeAction = () => continueCpuCycle(startIndex);
    return;
  }
  const cpuPlayers = ["right", "top", "left"];
  if (startIndex >= cpuPlayers.length) {
    startPlayerTurn("bottom");
    return;
  }
  if (state.wall.length <= 14) {
    endExhaustiveDraw();
    return;
  }

  const player = cpuPlayers[startIndex];
  state.pendingCpuIndex = startIndex + 1;
  state.current = player;
  const drawnTile = draw(player);
  if (drawnTile && isValidAgariForPlayer(player, "ツモ")) {
    showAgari(player, "ツモ", drawnTile);
    return;
  }
  log(`${playerName(player)} ツモ`);
  render();
  scheduleCpu(() => {
    if (state.paused) {
      state.resumeAction = () => continueCpuCycle(startIndex);
      return;
    }
    if (state.roundEnded || state.current !== player) return;
    const riichiDiscard = !state.riichiPlayers[player] ? findRiichiDiscardIndex(player) : -1;
    const declaredRiichi = riichiDiscard !== -1 && shouldCpuRiichi(player, waitsAfterDiscard(player, riichiDiscard));
    if (declaredRiichi) {
      declareRiichiFor(player);
      log(`${playerName(player)} リーチ`);
    }
    const index = declaredRiichi ? riichiDiscard : state.riichiPlayers[player] ? state.hands[player].length - 1 : chooseCpuDiscard(state.hands[player], player);
    const discarded = discardCpuTile(player, index);
    if (!discarded) {
      scheduleCpu(() => continueCpuCycle(startIndex + 1), 480);
      return;
    }

    if (state.current === "call" || state.current === "ron" || state.current === "ended") return;
    scheduleCpu(() => continueCpuCycle(startIndex + 1), 480);
  }, 360);
}

function startPlayerTurn(player) {
  if (state.paused) {
    state.resumeAction = () => startPlayerTurn(player);
    return;
  }
  state.current = player;
  state.callChoices = [];
  if (player === "bottom" && isCpuOnlyMode()) {
    continueCpuOnlyCycle(players.indexOf("bottom"));
    return;
  }
  if (player === "bottom" && state.hands.bottom.length === baseHandSize("bottom")) {
    if (state.wall.length <= 14) {
      endExhaustiveDraw();
      return;
    }
    draw("bottom");
    state.awaitingDraw = false;
    if (state.autoWin && canTsumo()) {
      declareTsumo();
      return;
    }
    if (state.riichi) {
      if (isValidAgariForPlayer("bottom", "ツモ")) {
        if (state.autoWin) {
          declareTsumo();
          return;
        }
        log("和了牌をツモりました。ツモ和了できます。");
        render();
        return;
      }

      state.autoTsumogiri = true;
      log("リーチ後のため自動ツモ切りします。");
      render();
      scheduleCpu(() => {
        if (state.paused) {
          state.resumeAction = () => {
            if (!state.autoTsumogiri || state.current !== "bottom" || state.roundEnded) return;
            discard("bottom", state.hands.bottom.length - 1);
            state.autoTsumogiri = false;
          };
          return;
        }
        if (!state.autoTsumogiri || state.current !== "bottom" || state.roundEnded) return;
        discard("bottom", state.hands.bottom.length - 1);
        state.autoTsumogiri = false;
      }, 420);
      return;
    }
    log("ツモりました。右端の牌、または手牌から1枚切ってください。");
  }
  render();
}
