function advanceAfterAgari() {
  if (state.gameEnded) {
    state.autoNextGameAt = 0;
    startGame();
    return;
  }
  $("scoreOverlay").hidden = true;
  const dealerWon = state.lastWinner === players[state.dealerIndex];
  state.honba = dealerWon ? state.honba + 1 : 0;
  if (!dealerWon) {
    advanceHand();
  }
  if (isGameComplete()) {
    showGameResult();
    return;
  }
  startRound();
}

function advanceHand() {
  state.dealerIndex = (state.dealerIndex + 1) % players.length;
  state.round += 1;
  if (state.round > 4) {
    state.round = 1;
    state.roundWindIndex += 1;
  }
}

function isGameComplete() {
  if (state.rules.tobi && players.some((player) => state.scores[player] < 0)) return true;
  const maxWindRounds = state.gameType === "hanchan" ? 2 : 1;
  return state.roundWindIndex >= maxWindRounds;
}

function showGameResult() {
  const trustBonus = settleFinalRiichiSticks();
  learnFromGameResult();
  finishPaifuGame({
    trustBonus,
    rankings: getRankedPlayers().map((player, index) => ({
      rank: index + 1,
      player,
      name: playerName(player),
      score: state.scores[player],
    })),
  });
  state.gameEnded = true;
  state.roundEnded = true;
  state.current = "ended";
  state.autoNextGameAt = isCpuOnlyMode() && state.rules.autoSelfPlay ? Date.now() + 1500 : 0;
  $("drawOverlay").hidden = true;
  $("resultTitle").textContent = "終局";
  $("resultDetail").textContent = `${gameTypeLabel()} 結果${trustBonus > 0 ? ` / 供託トップ取り +${trustBonus}点` : ""}${state.rules.cpuLearning ? ` / 学習 ${state.ai.games}試合` : ""}`;
  $("resultHand").innerHTML = "";
  $("resultYaku").innerHTML = getRankedPlayers()
    .map((player, index) => `<div>${index + 1}位 ${playerName(player)} ${state.scores[player]}</div>`)
    .join("");
  $("resultScores").innerHTML = "";
  $("nextRoundButton").textContent = "次局へ";
  $("scoreOverlay").hidden = false;
  log("試合終了です。結果を表示しました。");
  render();
  if (isCpuOnlyMode() && state.rules.autoSelfPlay && !state.cpuPumpTimer) {
    scheduleCpu(() => {
      if (state.paused) {
        state.resumeAction = startGame;
        return;
      }
      if (!state.rules.autoSelfPlay || !isCpuOnlyMode()) return;
      startGame();
    }, 1200);
  }
}

function settleFinalRiichiSticks() {
  if (state.riichiSticks <= 0) return 0;
  const bonus = state.riichiSticks * 1000;
  const top = getRankedPlayers()[0];
  state.scores[top] += bonus;
  state.riichiSticks = 0;
  return bonus;
}

function getRankedPlayers() {
  return [...players].sort((a, b) => state.scores[b] - state.scores[a]);
}

function declareKan() {
  const kanTiles = findKanTiles();
  if (kanTiles.length === 0) return;
  log(`槓候補: ${kanTiles.map((tile) => tile.mark).join(" / ")}。槓処理は次の実装対象です。`);
}
