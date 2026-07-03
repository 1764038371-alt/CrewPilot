function endExhaustiveDraw() {
  const scoreBefore = { ...state.scores };
  const tenpaiPlayers = players.filter((player) => safelyIsTenpai(player));
  const notenPlayers = players.filter((player) => !tenpaiPlayers.includes(player));
  settleNotenPayments(tenpaiPlayers, notenPlayers);
  try {
    learnFromRoundResult(scoreBefore, { tenpaiPlayers });
  } catch (error) {
    console.error(error);
    log(`流局時の学習処理をスキップしました: ${error.message}`);
    state.ai.roundDecisions = [];
  }

  players.forEach((player) => {
    state.revealedHands[player] = tenpaiPlayers.includes(player);
  });

  const dealer = players[state.dealerIndex];
  const dealerTenpai = tenpaiPlayers.includes(dealer);
  state.honba += 1;
  if (!dealerTenpai) {
    advanceHand();
  }
  state.pendingDrawGameEnd = isGameComplete();

  const tenpaiText = tenpaiPlayers.length ? tenpaiPlayers.map(playerName).join("、") : "なし";
  const nextDealer = state.pendingDrawGameEnd ? "試合終了" : playerName(players[state.dealerIndex]);
  log(`流局。聴牌: ${tenpaiText}。ノーテン罰符を精算しました。${state.pendingDrawGameEnd ? "試合終了です。" : `次局の親: ${nextDealer}`}`);
  try {
    finishPaifuRound({
      type: "ryukyoku",
      tenpaiPlayers,
      tenpaiNames: tenpaiPlayers.map(playerName),
      scores: { ...state.scores },
    });
  } catch (error) {
    console.error(error);
    log(`流局牌譜の保存をスキップしました: ${error.message}`);
  }
  state.current = "ended";
  state.roundEnded = true;
  state.lastWinner = null;
  state.callChoices = [];
  render();
  showDrawOverlay(tenpaiText, nextDealer);
}

function safelyIsTenpai(player) {
  try {
    return isTenpai(player);
  } catch (error) {
    console.error(error);
    log(`${playerName(player)}の聴牌判定をスキップしました: ${error.message}`);
    return false;
  }
}

function settleNotenPayments(tenpaiPlayers, notenPlayers) {
  if (tenpaiPlayers.length === 0 || tenpaiPlayers.length === 4) return;

  const gain = 3000 / tenpaiPlayers.length;
  const loss = 3000 / notenPlayers.length;
  tenpaiPlayers.forEach((player) => {
    state.scores[player] += gain;
  });
  notenPlayers.forEach((player) => {
    state.scores[player] -= loss;
  });
}

function showDrawOverlay(tenpaiText, nextDealer) {
  state.drawOk = { bottom: false, right: false, top: false, left: false };
  if (isCpuOnlyMode()) {
    $("drawOverlay").hidden = true;
    clearDrawTimer();
    scheduleCpu(() => {
      if (state.paused) {
        state.resumeAction = proceedAfterDraw;
        return;
      }
      proceedAfterDraw();
    }, cpuAutoAdvanceMs);
    return;
  }
  $("drawDetail").textContent = `聴牌: ${tenpaiText} / 次局の親: ${nextDealer}`;
  $("drawScores").innerHTML = players
    .map((player) => `<div>${playerName(player)} ${state.scores[player]}</div>`)
    .join("");
  $("drawOverlay").hidden = false;
  updateDrawOkStatus();
  clearDrawTimer();
  state.drawTimer = setTimeout(proceedAfterDraw, 5000);
}

function proceedAfterDraw() {
  if (state.paused) {
    state.resumeAction = proceedAfterDraw;
    return;
  }
  clearDrawTimer();
  $("drawOverlay").hidden = true;
  if (state.pendingDrawGameEnd) {
    showGameResult();
    return;
  }
  startRound();
}

function pressDrawOk(player = "bottom") {
  if ($("drawOverlay").hidden) return;
  state.drawOk[player] = true;
  updateDrawOkStatus();

  if (player === "bottom") {
    ["right", "top", "left"].forEach((cpu, index) => {
      setTimeout(() => {
        if ($("drawOverlay").hidden) return;
        state.drawOk[cpu] = true;
        updateDrawOkStatus();
        if (players.every((seat) => state.drawOk[seat])) {
          proceedAfterDraw();
        }
      }, 260 * (index + 1));
    });
  }

  if (players.every((seat) => state.drawOk[seat])) {
    proceedAfterDraw();
  }
}

function updateDrawOkStatus() {
  const okCount = players.filter((player) => state.drawOk[player]).length;
  $("drawOkStatus").textContent = `OK ${okCount} / 4`;
  $("drawOkButton").disabled = Boolean(state.drawOk.bottom);
}

function clearDrawTimer() {
  if (!state.drawTimer) return;
  clearTimeout(state.drawTimer);
  state.drawTimer = null;
}
