function startGame() {
  applyRuleForm();
  loadAiState();
  clearCpuTimer();
  clearCpuWatchdog();
  clearDrawTimer();
  $("scoreOverlay").hidden = true;
  $("drawOverlay").hidden = true;
  $("lobbyOverlay").hidden = true;
  state.gameStarted = true;
  state.gameType = state.rules.gameType;
  state.currentGameType = state.rules.gameType;
  state.viewSeat = "bottom";
  state.scores = Object.fromEntries(players.map((player) => [player, state.rules.initialPoints]));
  state.roundWindIndex = 0;
  state.dealerIndex = 0;
  state.round = 1;
  state.honba = 0;
  state.riichiSticks = 0;
  state.gameEnded = false;
  state.autoNextGameAt = 0;
  state.paused = false;
  state.resumeAction = null;
  state.pausedBeforeExitConfirm = false;
  state.pendingDrawGameEnd = false;
  state.ai.decisions = [];
  state.ai.roundDecisions = [];
  startPaifuGame();
  clearCpuHeartbeat();
  if (!isCpuOnlyMode()) {
    clearCpuPump();
  }
  startRound();
}

function defaultAiWeights() {
  return {
    waits: 80,
    tenpaiDraws: 120,
    pairs: 26,
    blocks: 18,
    isolated: -10,
    standardShanten: -180,
    chiitoiShanten: -60,
    callTaken: 12,
    callSkipped: 4,
    callShantenGain: 90,
    callYakuhai: 34,
    callHonitsu: 26,
    callIttsu: 20,
    callSanshoku: 18,
    callTanyao: 10,
    callYakuTenpai: 36,
    callFormalTenpai: 12,
    callAsDealer: 10,
    callAgainstDealer: 14,
    callNeedSpeed: 16,
    callNeedPoints: -6,
    callMiddleOrLater: 18,
    callLate: 24,
    callYakuWaitCount: 14,
    callFormalWaitCount: 7,
    yakuTenpaiKept: 220,
    openPlanKept: 70,
    openPlanBroken: -260,
    openPlanTenpai: 180,
    defenseSafe: 70,
    defenseDanger: -95,
    defenseFold: 80,
    defensePush: -18,
    defenseAgainstRiichi: 24,
    defenseDoraDanger: -55,
    riichiDeclared: 16,
    damaChosen: 4,
    riichiGoodWait: 18,
    riichiBadWait: -8,
    riichiNeedPoints: 18,
    riichiAsDealer: 10,
    riichiTopLate: -18,
    terminalHonorDiscard: 3,
    honorDiscard: 5,
  };
}

function loadAiState() {
  if (state.ai.weights) return;
  try {
    const saved = JSON.parse(localStorage.getItem("mahjongAiState") || "null");
    state.ai.weights = { ...defaultAiWeights(), ...(saved?.weights ?? {}) };
    state.ai.games = saved?.games ?? 0;
    state.ai.gamesByType = {
      tonpuu: saved?.gamesByType?.tonpuu ?? 0,
      hanchan: saved?.gamesByType?.hanchan ?? 0,
    };
  } catch {
    state.ai.weights = defaultAiWeights();
    state.ai.games = 0;
    state.ai.gamesByType = { tonpuu: 0, hanchan: 0 };
  }
}

function saveAiState() {
  try {
    localStorage.setItem("mahjongAiState", JSON.stringify({
      weights: state.ai.weights,
      games: state.ai.games,
      gamesByType: state.ai.gamesByType,
    }));
  } catch (error) {
    console.error(error);
    log(`学習データ保存に失敗しました: ${error.message}`);
  }
}

function applyRuleForm() {
  if ($("lobbyOverlay")?.hidden && state.gameStarted) {
    state.rules.gameType = state.currentGameType || state.rules.gameType;
    return;
  }
  state.rules.gameType = $("ruleGameType").value;
  state.rules.seatMode = $("ruleSeatMode").value;
  state.rules.initialPoints = Number($("ruleInitialPoints").value);
  state.rules.redDora = $("ruleRedDora").value === "on";
  state.rules.tobi = $("ruleTobi").value === "on";
  state.rules.abortiveDraws = $("ruleAbortiveDraws").value === "on";
  state.rules.agariYame = $("ruleAgariYame").value === "on";
  state.rules.cpuAttack = $("ruleCpuAttack").value;
  state.rules.cpuLearning = $("ruleCpuLearning").value === "on";
  state.rules.learningMode = $("ruleLearningMode").value;
  state.rules.autoSelfPlay = $("ruleAutoSelfPlay").value === "on";
}

function syncRuleForm() {
  $("ruleGameType").value = state.rules.gameType;
  $("ruleSeatMode").value = state.rules.seatMode;
  $("ruleInitialPoints").value = String(state.rules.initialPoints);
  $("ruleRedDora").value = state.rules.redDora ? "on" : "off";
  $("ruleTobi").value = state.rules.tobi ? "on" : "off";
  $("ruleAbortiveDraws").value = state.rules.abortiveDraws ? "on" : "off";
  $("ruleAgariYame").value = state.rules.agariYame ? "on" : "off";
  $("ruleCpuAttack").value = state.rules.cpuAttack;
  $("ruleCpuLearning").value = state.rules.cpuLearning ? "on" : "off";
  $("ruleLearningMode").value = state.rules.learningMode;
  $("ruleAutoSelfPlay").value = state.rules.autoSelfPlay ? "on" : "off";
}

function openLobby() {
  loadAiState();
  syncRuleForm();
  renderLearningSummary();
  renderPaifuIndex();
  $("lobbyOverlay").hidden = false;
}

function closeLobby() {
  if (!state.gameStarted) {
    startGame();
    return;
  }
  $("lobbyOverlay").hidden = true;
}

function buildWall() {
  const wall = [];

  suits.forEach((suit) => {
    suit.marks.forEach((mark, index) => {
      for (let copy = 0; copy < 4; copy += 1) {
        wall.push({
          id: `${suit.key}${index + 1}-${copy}`,
          tileIndex: suit.order * 9 + index,
          order: suit.order * 100 + index,
          mark,
          tone: state.rules.redDora && copy === 0 && index === 4 ? "flower" : suit.tone,
          suit: suit.key,
          number: index + 1,
        });
      }
    });
  });

  honors.forEach((honor, index) => {
    for (let copy = 0; copy < 4; copy += 1) {
      wall.push({
        id: `${honor.id}-${copy}`,
        tileIndex: 27 + index,
        order: 300 + index,
        mark: honor.mark,
        tone: honor.tone,
        suit: "z",
        number: index + 1,
      });
    }
  });

  return shuffle(wall);
}

function shuffle(items) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [result[index], result[swapIndex]] = [result[swapIndex], result[index]];
  }
  return result;
}
